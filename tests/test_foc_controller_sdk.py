import argparse
import ctypes
import time

DRV_SUCCESS = 20002
DRV_ACQUIRING = 20072
DRV_IDLE = 20073
DRV_TEMP_STABILIZED = 20036
DRV_TEMP_NOT_REACHED = 20037

DEFAULT_DLL_PATH = "C:\\Program Files\\Andor SDK\\atmcd64d.dll"


def _as_value(value):
    return value.value if hasattr(value, "value") else value


def _write_scalar(pointer, value):
    if hasattr(pointer, "_obj"):
        pointer._obj.value = value
        return
    if hasattr(pointer, "contents"):
        pointer.contents.value = value
        return
    raise TypeError(f"Cannot write output value into pointer type: {type(pointer)!r}")


class _MockFunction:
    def __init__(self, name, simulator):
        self.name = name
        self.simulator = simulator
        self.argtypes = None
        self.restype = ctypes.c_uint

    def __call__(self, *args):
        return self.simulator.call(self.name, args)


class FocCameraSimulator:
    """Stateful simulator for common Andor/FOC camera SDK2-style calls."""

    def __init__(self):
        self.initialized = False
        self.available_cameras = 1
        self.current_camera = 0
        self.handles = [101]
        self.cooler_on = False
        self.target_temperature = -70
        self.current_temperature = 20.0
        self.exposure_seconds = 0.1
        self.acquiring = False
        self.readout_width = 512
        self.readout_height = 512
        self.last_frame = [0] * (self.readout_width * self.readout_height)
        self._acq_start = 0.0
        self._acq_counter = 0

    def _generate_frame(self):
        pixels = self.readout_width * self.readout_height
        phase = self._acq_counter * 31
        self.last_frame = [((i + phase) % 65535) for i in range(pixels)]

    def call(self, name, args):
        handler = getattr(self, f"_handle_{name}", None)
        if handler is not None:
            return handler(args)
        # Default success for unimplemented SDK calls to keep integration flow unblocked.
        return DRV_SUCCESS

    def _handle_Initialize(self, _args):
        self.initialized = True
        return DRV_SUCCESS

    def _handle_ShutDown(self, _args):
        self.initialized = False
        self.acquiring = False
        return DRV_SUCCESS

    def _handle_GetAvailableCameras(self, args):
        _write_scalar(args[0], self.available_cameras)
        return DRV_SUCCESS

    def _handle_GetCameraHandle(self, args):
        index = int(_as_value(args[0]))
        handle = self.handles[index] if 0 <= index < len(self.handles) else -1
        _write_scalar(args[1], handle)
        return DRV_SUCCESS

    def _handle_SetCurrentCamera(self, args):
        handle = int(_as_value(args[0]))
        if handle in self.handles:
            self.current_camera = self.handles.index(handle)
        return DRV_SUCCESS

    def _handle_GetCurrentCamera(self, args):
        _write_scalar(args[0], self.handles[self.current_camera])
        return DRV_SUCCESS

    def _handle_CoolerON(self, _args):
        self.cooler_on = True
        return DRV_SUCCESS

    def _handle_CoolerOFF(self, _args):
        self.cooler_on = False
        return DRV_SUCCESS

    def _handle_IsCoolerOn(self, args):
        _write_scalar(args[0], 1 if self.cooler_on else 0)
        return DRV_SUCCESS

    def _handle_SetTemperature(self, args):
        self.target_temperature = int(_as_value(args[0]))
        return DRV_SUCCESS

    def _handle_GetTemperature(self, args):
        ambient = 20.0
        pull = self.target_temperature if self.cooler_on else ambient
        delta = pull - self.current_temperature
        step = 1.5 if self.cooler_on else 0.8
        if abs(delta) <= step:
            self.current_temperature = float(pull)
        else:
            self.current_temperature += step if delta > 0 else -step
        _write_scalar(args[0], int(round(self.current_temperature)))
        if self.cooler_on and abs(self.current_temperature - self.target_temperature) <= 1.0:
            return DRV_TEMP_STABILIZED
        return DRV_TEMP_NOT_REACHED

    def _handle_SetExposureTime(self, args):
        self.exposure_seconds = float(_as_value(args[0]))
        return DRV_SUCCESS

    def _handle_SetAcquisitionMode(self, _args):
        return DRV_SUCCESS

    def _handle_SetReadMode(self, _args):
        return DRV_SUCCESS

    def _handle_SetTriggerMode(self, _args):
        return DRV_SUCCESS

    def _handle_SetImage(self, args):
        hstart = int(_as_value(args[2]))
        hend = int(_as_value(args[3]))
        vstart = int(_as_value(args[4]))
        vend = int(_as_value(args[5]))
        self.readout_width = max(1, hend - hstart + 1)
        self.readout_height = max(1, vend - vstart + 1)
        return DRV_SUCCESS

    def _handle_GetDetector(self, args):
        _write_scalar(args[0], self.readout_width)
        _write_scalar(args[1], self.readout_height)
        return DRV_SUCCESS

    def _handle_StartAcquisition(self, _args):
        self.acquiring = True
        self._acq_start = time.time()
        self._acq_counter += 1
        return DRV_SUCCESS

    def _handle_AbortAcquisition(self, _args):
        self.acquiring = False
        return DRV_SUCCESS

    def _handle_GetStatus(self, args):
        if self.acquiring and (time.time() - self._acq_start) >= max(0.0, self.exposure_seconds):
            self.acquiring = False
            self._generate_frame()
        _write_scalar(args[0], DRV_ACQUIRING if self.acquiring else DRV_IDLE)
        return DRV_SUCCESS

    def _handle_WaitForAcquisition(self, _args):
        if self.acquiring:
            elapsed = time.time() - self._acq_start
            wait_left = max(0.0, self.exposure_seconds - elapsed)
            if wait_left > 0:
                time.sleep(wait_left)
            self.acquiring = False
            self._generate_frame()
        return DRV_SUCCESS

    def _handle_GetAcquiredData(self, args):
        out_ptr = args[0]
        pixel_count = int(_as_value(args[1]))
        data = self.last_frame[:pixel_count]
        if len(data) < pixel_count:
            data.extend([0] * (pixel_count - len(data)))
        out = ctypes.cast(out_ptr, ctypes.POINTER(ctypes.c_long))
        for i in range(pixel_count):
            out[i] = int(data[i])
        return DRV_SUCCESS


class MockAtmcdDLL:
    def __init__(self, simulator):
        self._simulator = simulator
        self._functions = {}

    def __getattr__(self, name):
        if name not in self._functions:
            self._functions[name] = _MockFunction(name, self._simulator)
        return self._functions[name]


def load_driver(simulate, dll_path):
    if not simulate:
        try:
            return ctypes.WinDLL(dll_path), False
        except OSError as exc:
            print(f"Real DLL load failed ({exc}). Falling back to simulator mode.")
    return MockAtmcdDLL(FocCameraSimulator()), True


def main():
    parser = argparse.ArgumentParser(
        description="Exercise Andor/FOC camera functions in real or simulated mode."
    )
    parser.add_argument("--simulate", action="store_true", help="Force simulator mode.")
    parser.add_argument("--dll-path", default=DEFAULT_DLL_PATH, help="Path to atmcd64d.dll")
    args = parser.parse_args()

    dll, simulated = load_driver(args.simulate, args.dll_path)
    print(f"Driver object: {type(dll).__name__}")
    print("Mode:", "SIMULATED" if simulated else "REAL")

    Initialize = dll.Initialize
    Initialize.argtypes = [ctypes.c_char_p]
    Initialize.restype = ctypes.c_uint

    GetAvailableCameras = dll.GetAvailableCameras
    GetAvailableCameras.argtypes = [ctypes.POINTER(ctypes.c_long)]
    GetAvailableCameras.restype = ctypes.c_uint

    CoolerON = dll.CoolerON
    CoolerON.restype = ctypes.c_uint

    SetTemperature = dll.SetTemperature
    SetTemperature.argtypes = [ctypes.c_int]
    SetTemperature.restype = ctypes.c_uint

    GetTemperature = dll.GetTemperature
    GetTemperature.argtypes = [ctypes.POINTER(ctypes.c_int)]
    GetTemperature.restype = ctypes.c_uint

    SetExposureTime = dll.SetExposureTime
    SetExposureTime.argtypes = [ctypes.c_float]
    SetExposureTime.restype = ctypes.c_uint

    StartAcquisition = dll.StartAcquisition
    StartAcquisition.restype = ctypes.c_uint

    WaitForAcquisition = dll.WaitForAcquisition
    WaitForAcquisition.restype = ctypes.c_uint

    GetStatus = dll.GetStatus
    GetStatus.argtypes = [ctypes.POINTER(ctypes.c_int)]
    GetStatus.restype = ctypes.c_uint

    GetDetector = dll.GetDetector
    GetDetector.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    GetDetector.restype = ctypes.c_uint

    GetAcquiredData = dll.GetAcquiredData
    GetAcquiredData.argtypes = [ctypes.POINTER(ctypes.c_long), ctypes.c_long]
    GetAcquiredData.restype = ctypes.c_uint

    ret = Initialize(b"")
    print("Initialize:", ret)

    num = ctypes.c_long()
    ret = GetAvailableCameras(ctypes.byref(num))
    print("GetAvailableCameras:", ret, "count=", num.value)

    ret = CoolerON()
    print("CoolerON:", ret)
    ret = SetTemperature(-70)
    print("SetTemperature:", ret)

    temp = ctypes.c_int()
    for _ in range(3):
        ret = GetTemperature(ctypes.byref(temp))
        print("GetTemperature:", ret, "temp=", temp.value)

    ret = SetExposureTime(ctypes.c_float(0.2))
    print("SetExposureTime:", ret)
    ret = StartAcquisition()
    print("StartAcquisition:", ret)

    status = ctypes.c_int()
    ret = GetStatus(ctypes.byref(status))
    print("GetStatus(before wait):", ret, "status=", status.value)

    ret = WaitForAcquisition()
    print("WaitForAcquisition:", ret)
    ret = GetStatus(ctypes.byref(status))
    print("GetStatus(after wait):", ret, "status=", status.value)

    xpix = ctypes.c_int()
    ypix = ctypes.c_int()
    ret = GetDetector(ctypes.byref(xpix), ctypes.byref(ypix))
    print("GetDetector:", ret, "size=", (xpix.value, ypix.value))

    count = xpix.value * ypix.value
    frame = (ctypes.c_long * count)()
    ret = GetAcquiredData(frame, count)
    print("GetAcquiredData:", ret, "first10=", list(frame[:10]))


if __name__ == "__main__":
    main()