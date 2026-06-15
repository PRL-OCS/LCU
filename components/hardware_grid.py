import time
from nicegui import ui

def format_ra(deg):
    hours = deg / 15.0
    h = int(hours)
    m = int((hours - h) * 60)
    s = (hours - h - m/60.0) * 3600
    return f"{h:02d}h {m:02d}m {s:04.1f}s"

def format_dec(deg):
    sign = '+' if deg >= 0 else '-'
    deg = abs(deg)
    d = int(deg)
    m = int((deg - d) * 60)
    s = (deg - d - m/60.0) * 3600
    return f"{sign}{d:02d}° {m:02d}' {s:04.1f}\""

def render_hardware_grid():
    hardware_container = ui.element('div').classes('grid grid-cols-1 xl:grid-cols-2 gap-gutter w-full')
    hardware_container._ui_elements = {}
    hardware_container._topology_cache = None
    return hardware_container

def _build_dom(hardware_container, status):
    hardware_container.clear()
    hardware_container._ui_elements.clear()
    
    t_plugins = status.get('telescope_plugins', {})
    i_plugins = status.get('instrument_plugins', {})
    hardware_mapping = status.get('hardware_mapping', {})
    
    hardware_container._topology_cache = (list(t_plugins.keys()), list(i_plugins.keys()), hardware_mapping)
    
    telescope_to_instruments = {t: [] for t in t_plugins.keys()}
    unmapped_instruments = []
    for i_name, t_name in hardware_mapping.items():
        if i_name in i_plugins:
            if t_name in telescope_to_instruments:
                telescope_to_instruments[t_name].append(i_name)
            else:
                unmapped_instruments.append(i_name)
                
    for i_name in i_plugins:
        if i_name not in hardware_mapping:
            unmapped_instruments.append(i_name)

    with hardware_container:
        for t_id in t_plugins.keys():
            with ui.column().classes('glass-panel panel-border rounded-xl overflow-hidden flex flex-col p-0 gap-0 w-full'):
                with ui.row().classes('w-full p-md border-b border-outline-variant flex justify-between items-center bg-surface-container-low m-0'):
                    ui.label(f'{t_id} Subsystem').classes('font-headline-sm text-headline-sm font-bold text-on-surface')
                    ui.label('ONLINE').classes('px-sm py-base bg-secondary-container/20 text-secondary text-label-sm font-label-sm rounded border border-secondary/30')
                
                with ui.element('div').classes('p-md grid grid-cols-1 md:grid-cols-2 gap-md w-full'):
                    # Left Column: Status
                    with ui.column().classes('space-y-sm p-0 w-full'):
                        # Telescope Status
                        with ui.column().classes('bg-background/40 p-md rounded-xl border border-outline-variant/30 w-full'):
                            ui.label('Telescope Status').classes('text-label-sm font-label-sm text-on-surface-variant uppercase mb-xs block')
                            with ui.row().classes('flex items-baseline gap-sm mb-md'):
                                hardware_container._ui_elements[f'{t_id}_state'] = ui.label('IDLE').classes('text-headline-md font-headline-md text-on-surface')
                                hardware_container._ui_elements[f'{t_id}_indicator'] = ui.element('span').classes('w-2 h-2 rounded-full bg-secondary-fixed')
                            
                            with ui.column().classes('space-y-xs w-full gap-2'):
                                with ui.row().classes('flex justify-between terminal-bg p-xs rounded border border-outline-variant/20 w-full items-center'):
                                    ui.label('RA:').classes('text-label-sm font-label-sm text-on-surface-variant')
                                    hardware_container._ui_elements[f'{t_id}_ra'] = ui.label('').classes('font-data-mono text-data-mono text-primary')
                                with ui.row().classes('flex justify-between terminal-bg p-xs rounded border border-outline-variant/20 w-full items-center'):
                                    ui.label('DEC:').classes('text-label-sm font-label-sm text-on-surface-variant')
                                    hardware_container._ui_elements[f'{t_id}_dec'] = ui.label('').classes('font-data-mono text-data-mono text-primary')
<<<<<<< HEAD
                                
=======
>>>>>>> 0882ff1 (added tests and improved the UI)
                                # Dynamic Extra Telemetry fields
                                hardware_container._ui_elements[f'{t_id}_extra_telemetry'] = ui.column().classes('space-y-xs w-full gap-2')
                        
                        # Instrument Status
                        for i_id in telescope_to_instruments[t_id]:
                            with ui.column().classes('bg-background/40 p-md rounded-xl border border-outline-variant/30 w-full'):
                                ui.label(f'Instrument: {i_id}').classes('text-label-sm font-label-sm text-on-surface-variant uppercase mb-xs block')
                                hardware_container._ui_elements[f'{i_id}_state'] = ui.label('IDLE').classes('text-headline-md font-headline-md text-on-surface')
                                
                                hardware_container._ui_elements[f'{i_id}_prog_container'] = ui.column().classes('w-full mt-2').style('display: none')
                                with hardware_container._ui_elements[f'{i_id}_prog_container']:
                                    hardware_container._ui_elements[f'{i_id}_prog'] = ui.linear_progress(0.0, show_value=False, color='primary').classes('w-full h-2 rounded')
                                    hardware_container._ui_elements[f'{i_id}_prog_text'] = ui.label('').classes('text-label-sm font-label-sm text-on-surface-variant mt-1')

                    # Right Column: Pipeline Details
                    with ui.column().classes('space-y-sm p-0 w-full h-full'):
                        with ui.column().classes('bg-background/40 p-md rounded-xl border border-outline-variant/30 h-full w-full'):
                            ui.label('Pipeline Details').classes('text-label-sm font-label-sm text-on-surface-variant uppercase mb-sm block')
                            
                            hardware_container._ui_elements[f'{t_id}_active_target_container'] = ui.column().classes('p-md border border-dashed border-outline rounded flex flex-col items-center justify-center text-center py-xl w-full h-full')
                            with hardware_container._ui_elements[f'{t_id}_active_target_container']:
                                hardware_container._ui_elements[f'{t_id}_active_icon'] = ui.icon('inbox').classes('text-outline-variant mb-sm text-3xl')
                                hardware_container._ui_elements[f'{t_id}_active_target'] = ui.label('No active target in queue').classes('text-label-md font-label-md text-on-surface-variant')
                                ui.button('LOAD SEQUENCE').classes('mt-md text-primary font-label-sm text-label-sm border border-primary/30 px-sm py-base rounded hover:bg-primary/10 transition-colors bg-transparent shadow-none')
                                
                            for i_id in telescope_to_instruments[t_id]:
                                hardware_container._ui_elements[f'{i_id}_queue_container'] = ui.scroll_area().classes('w-full h-24 mt-2 border border-outline-variant/20 terminal-bg p-2 rounded').style('display: none')
                                with hardware_container._ui_elements[f'{i_id}_queue_container']:
                                    hardware_container._ui_elements[f'{i_id}_queue_items'] = ui.label('').classes('text-xs text-on-surface-variant font-mono tracking-wider')

        if unmapped_instruments:
            with ui.column().classes('glass-panel panel-border rounded-xl overflow-hidden flex flex-col p-0 gap-0 w-full border-error'):
                with ui.row().classes('w-full p-md border-b border-error/50 flex justify-between items-center bg-error-container/20 m-0'):
                    ui.label('Unmapped Instruments').classes('font-headline-sm text-headline-sm font-bold text-error')
                with ui.element('div').classes('p-md grid grid-cols-1 md:grid-cols-2 gap-md w-full'):
                    for i_id in unmapped_instruments:
                        with ui.column().classes('bg-background/40 p-md rounded-xl border border-outline-variant/30 w-full'):
                            ui.label(f'Instrument: {i_id}').classes('text-label-sm font-label-sm text-on-surface-variant uppercase mb-xs block')
                            hardware_container._ui_elements[f'{i_id}_state'] = ui.label('ORPHANED').classes('text-headline-md font-headline-md text-on-surface')


def update_hardware_grid(hardware_container, status):
    t_plugins = status.get('telescope_plugins', {})
    i_plugins = status.get('instrument_plugins', {})
    hardware_mapping = status.get('hardware_mapping', {})
    
    current_topology = (list(t_plugins.keys()), list(i_plugins.keys()), hardware_mapping)
    if getattr(hardware_container, '_topology_cache', None) != current_topology:
        _build_dom(hardware_container, status)
        
    telescope_to_instruments = {t: [] for t in t_plugins.keys()}
    for i_name, t_name in hardware_mapping.items():
        if i_name in i_plugins and t_name in telescope_to_instruments:
            telescope_to_instruments[t_name].append(i_name)

    executors = status.get('executors', {})
    
    for t_id in t_plugins.keys():
        t_exec = executors.get(t_id, {})
        is_running = t_exec.get('running', False)
        raw_state = t_exec.get('current_state', 'IDLE')
        current_obs = t_exec.get('current_obs_id', None)
        
        t_state = raw_state
        if raw_state in ['CONFIGURING', 'EXPOSING', 'READING_OUT']:
            t_state = 'TRACKING'
        elif raw_state == 'DONE':
            t_state = 'IDLE'
            
        t_color = 'text-primary' if is_running and t_state != 'IDLE' else 'text-on-surface'
        t_indicator = 'bg-primary' if is_running and t_state != 'IDLE' else 'bg-secondary-fixed'
        if t_state in ['FAILED', 'ABORTED']:
            t_color = 'text-error'
            t_indicator = 'bg-error'
        elif t_state == 'SLEWING':
            t_color = 'text-tertiary'
            t_indicator = 'bg-tertiary'
            
        hardware_container._ui_elements[f'{t_id}_state'].set_text(t_state)
        hardware_container._ui_elements[f'{t_id}_state'].classes(replace=f'text-headline-md font-headline-md {t_color}')
        hardware_container._ui_elements[f'{t_id}_indicator'].classes(replace=f'w-2 h-2 rounded-full {t_indicator}')
        
        current_ra = t_exec.get('current_ra')
        current_dec = t_exec.get('current_dec')
        if current_ra is not None and current_dec is not None:
            hardware_container._ui_elements[f'{t_id}_ra'].set_text(f'{format_ra(current_ra)}')
            hardware_container._ui_elements[f'{t_id}_dec'].set_text(f'{format_dec(current_dec)}')
            
        # Update extra telemetry
        extra_container = hardware_container._ui_elements.get(f'{t_id}_extra_telemetry')
        if extra_container:
            keys_to_exclude = {
                "telescope_id", "running", "queue_size", "current_obs_id", 
                "current_state", "current_ra", "current_dec", "exposure_start_time", 
                "exposure_duration", "ra", "dec"
            }
            
            extra_items = []
            for k, v in t_exec.items():
                if k in keys_to_exclude:
                    continue
                # Map raw keys to user-friendly titles and format values
                title = k.replace('_', ' ').replace('is ', '').title()
                if title == 'Connected':
                    title = 'Telescope'
                elif title == 'Skychart Online':
                    title = 'Skychart Connection'
                elif title == 'Dome Status':
                    title = 'Dome'
                
                extra_items.append((title, v))
                
            current_state_str = str(sorted(extra_items, key=lambda x: x[0]))
            last_state_str = getattr(extra_container, '_last_rendered_state', None)
            
            if current_state_str != last_state_str:
                extra_container.clear()
                with extra_container:
                    for title, val in extra_items:
                        with ui.row().classes('flex justify-between terminal-bg p-xs rounded border border-outline-variant/20 w-full items-center'):
                            ui.label(f'{title}:').classes('text-label-sm font-label-sm text-on-surface-variant')
                            
                            if isinstance(val, bool):
                                if title == 'Slewing':
                                    color = 'text-tertiary font-bold' if val else 'text-on-surface-variant'
                                    text = 'YES' if val else 'NO'
                                elif title == 'Tracking':
                                    color = 'text-[#10B981]' if val else 'text-on-surface-variant'
                                    text = 'ON' if val else 'OFF'
                                else:
                                    color = 'text-[#10B981]' if val else 'text-red-400 font-bold'
                                    if 'Connection' in title:
                                        text = 'ONLINE' if val else 'OFFLINE'
                                    elif 'Connected' in title or title == 'Telescope':
                                        text = 'CONNECTED' if val else 'DISCONNECTED'
                                    else:
                                        text = 'ON' if val else 'OFF'
                                ui.label(text).classes(f'font-data-mono text-data-mono {color}')
                            elif isinstance(val, (int, float)) and ('ra' in title.lower() or 'dec' in title.lower()):
                                formatted_val = format_ra(val) if 'ra' in title.lower() else format_dec(val)
                                ui.label(formatted_val).classes('font-data-mono text-data-mono text-primary')
                            else:
                                ui.label(str(val).upper()).classes('font-data-mono text-data-mono text-primary')
                extra_container._last_rendered_state = current_state_str
            
        if current_obs and raw_state != 'IDLE':
            hardware_container._ui_elements[f'{t_id}_active_target_container'].classes(replace='p-md border border-primary/50 bg-primary/10 rounded flex flex-col items-center justify-center text-center py-xl w-full h-full')
            hardware_container._ui_elements[f'{t_id}_active_icon'].classes(replace='text-primary mb-sm text-3xl')
            hardware_container._ui_elements[f'{t_id}_active_icon']._props['name'] = 'track_changes'
            hardware_container._ui_elements[f'{t_id}_active_target'].set_text(f'Tracking: {current_obs}').classes(replace='text-label-md font-label-md text-primary')
        else:
            hardware_container._ui_elements[f'{t_id}_active_target_container'].classes(replace='p-md border border-dashed border-outline rounded flex flex-col items-center justify-center text-center py-xl w-full h-full')
            hardware_container._ui_elements[f'{t_id}_active_icon'].classes(replace='text-outline-variant mb-sm text-3xl')
            hardware_container._ui_elements[f'{t_id}_active_icon']._props['name'] = 'inbox'
            hardware_container._ui_elements[f'{t_id}_active_target'].set_text('No active target in queue').classes(replace='text-label-md font-label-md text-on-surface-variant')
            
        # Update extra telemetry
        extra_container = hardware_container._ui_elements.get(f'{t_id}_extra_telemetry')
        if extra_container:
            keys_to_exclude = {
                "telescope_id", "running", "queue_size", "current_obs_id", 
                "current_state", "current_ra", "current_dec", "exposure_start_time", 
                "exposure_duration", "ra", "dec"
            }
            
            extra_items = []
            for k, v in t_exec.items():
                if k in keys_to_exclude:
                    continue
                # Map raw keys to user-friendly titles and format values
                title = k.replace('_', ' ').replace('is ', '').title()
                if title == 'Connected':
                    title = 'Telescope Connected'
                elif title == 'Skychart Online':
                    title = 'Skychart Connection'
                elif title == 'Dome Status':
                    title = 'Dome'
                
                extra_items.append((title, v))
                
            current_state_str = str(sorted(extra_items, key=lambda x: x[0]))
            last_state_str = getattr(extra_container, '_last_rendered_state', None)
            
            if current_state_str != last_state_str:
                extra_container.clear()
                with extra_container:
                    for title, val in extra_items:
                        with ui.row().classes('flex justify-between terminal-bg p-xs rounded border border-outline-variant/20 w-full items-center'):
                            ui.label(f'{title}:').classes('text-label-sm font-label-sm text-on-surface-variant')
                            
                            if isinstance(val, bool):
                                color = 'text-[#10B981]' if val else 'text-red-400 font-bold'
                                text = 'CONNECTED' if 'Connected' in title or 'Connection' in title else ('ON' if val else 'OFF')
                                if 'Connection' in title:
                                    text = 'ONLINE' if val else 'OFFLINE'
                                ui.label(text).classes(f'font-data-mono text-data-mono {color}')
                            elif isinstance(val, (int, float)) and ('ra' in title.lower() or 'dec' in title.lower()):
                                formatted_val = format_ra(val) if 'ra' in title.lower() else format_dec(val)
                                ui.label(formatted_val).classes('font-data-mono text-data-mono text-primary')
                            else:
                                ui.label(str(val).upper()).classes('font-data-mono text-data-mono text-primary')
                extra_container._last_rendered_state = current_state_str

        # Update instruments
        for i_id in telescope_to_instruments[t_id]:
            if f'{i_id}_state' in hardware_container._ui_elements:
                i_state = 'IDLE'
                raw_i_state = executors.get(t_id, {}).get('current_state', 'IDLE')
                if raw_i_state in ['CONFIGURING', 'EXPOSING', 'READING_OUT', 'FAILED', 'ABORTED']:
                    i_state = raw_i_state
                    
                i_color = 'text-on-surface'
                if i_state in ['CONFIGURING', 'EXPOSING', 'READING_OUT']:
                    i_color = 'text-tertiary'
                elif i_state in ['FAILED', 'ABORTED']:
                    i_color = 'text-error'
                    
                hardware_container._ui_elements[f'{i_id}_state'].set_text(i_state).classes(replace=f'text-headline-md font-headline-md {i_color}')
                
                exposure_start = executors.get(t_id, {}).get('exposure_start_time')
                exposure_dur = executors.get(t_id, {}).get('exposure_duration')
                if i_state == 'EXPOSING' and exposure_start and exposure_dur:
                    elapsed = time.time() - exposure_start
                    progress = min(max(elapsed / exposure_dur, 0.0), 1.0)
                    hardware_container._ui_elements[f'{i_id}_prog'].value = progress
                    hardware_container._ui_elements[f'{i_id}_prog_text'].set_text(f'{elapsed:.1f}s / {exposure_dur}s')
                    hardware_container._ui_elements[f'{i_id}_prog_container'].style('display: flex')
                else:
                    hardware_container._ui_elements[f'{i_id}_prog_container'].style('display: none')
                    
                i_status = i_plugins.get(i_id, {})
                q_items = i_status.get('queued_items', [])
                q_size = i_status.get('queue_size', 0)
                if q_size > 0:
                    hardware_container._ui_elements[f'{i_id}_queue_container'].style('display: block')
                    if q_items:
                        hardware_container._ui_elements[f'{i_id}_queue_items'].set_text('\n'.join(q_items))
                else:
                    hardware_container._ui_elements[f'{i_id}_queue_container'].style('display: none')
