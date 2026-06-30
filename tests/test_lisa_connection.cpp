#include <iostream>
#include <string>
#include "AtikCameras.h"

using namespace std;

int main() {
    cout << "========================================\n";
    cout << "   LISA CONNECTION TEST (MINIMUM RISK)\n";
    cout << "========================================\n\n";

    // 1. Load the SDK DLL
#ifdef _WIN32
    string dllName = "AtikCameras.dll";
#else
    string dllName = "libatikcameras.so";
#endif

    if (!ArtemisLoadDLL(dllName.c_str())) {
        cout << "[ERROR] Could not find " << dllName << ". Make sure it is in the same folder.\n";
        return 1;
    }
    
    // 2. Check for connected devices
    int devCount = ArtemisDeviceCount();
    if (devCount == 0) {
        cout << "[ERROR] No hardware detected. Please check LISA's USB and power cables.\n";
        return 1;
    }
    
    cout << "[SUCCESS] Found " << devCount << " Atik device(s) connected to the USB bus!\n\n";
    cout << "Attempting to open communication with LISA...\n";

    // 3. Connect to the first camera
    ArtemisHandle handle = ArtemisConnect(0);
    if (handle == NULL) {
        cout << "[ERROR] Found the device, but failed to open a connection handle.\n";
        return 1;
    }

    // 4. Retrieve and print camera properties to verify it's responding
    ARTEMISPROPERTIES props;
    if (ArtemisProperties(handle, &props) == ARTEMIS_OK) {
        cout << "[SUCCESS] Connection to LISA established!\n";
        cout << "  -> Camera Model:  " << props.Description << "\n";
        cout << "  -> Resolution:    " << props.nPixelsX << " x " << props.nPixelsY << " pixels\n";
        cout << "  -> Pixel Size:    " << props.PixelMicronsX << " x " << props.PixelMicronsY << " um\n";
    } else {
        cout << "[WARNING] Connected, but could not read camera properties.\n";
    }

    // 5. Disconnect immediately to ensure absolute safety
    cout << "\nClosing connection to ensure minimum risk...\n";
    ArtemisDisconnect(handle);
    cout << "[SUCCESS] Disconnected cleanly.\n";
    cout << "Test completed safely.\n";

    return 0;
}
