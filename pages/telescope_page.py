from nicegui import ui
import asyncio
import json
from core.orchestrator import orchestrator
from components.hardware_grid import format_ra, format_dec
from components.log_console import render_log_console, update_log_console

def build_telescope_page(telescope_id: str):
    ui.add_head_html(open('stitch_theme.html').read())
    ui.dark_mode().enable()
    ui.colors(primary='#a7caec', secondary='#b5ccc1', accent='#ebbf8e', dark='#111318', positive='#b5ccc1', negative='#ffb4ab', warning='#ebbf8e', info='#a7caec')
    
    # Header
    with ui.header().classes('bg-surface-container fixed top-0 w-full z-50 border-b border-outline-variant flex justify-between items-center px-md h-16 transition-colors duration-200 ease-in-out'):
        with ui.row().classes('flex items-center gap-md'):
            ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/')).classes('text-primary hover:bg-surface-container-highest transition-colors cursor-pointer bg-transparent shadow-none')
            ui.label(f'Telescope {telescope_id}').classes('font-headline-sm text-headline-sm font-semibold text-on-surface')
            
        with ui.row().classes('flex items-center gap-md'):
            status_badge = ui.label('UNKNOWN').classes('text-label-md font-label-md px-md py-1.5 glass-panel panel-border rounded-full tracking-wider uppercase')
            ui.icon('settings').classes('p-base text-on-surface-variant hover:bg-surface-container-highest transition-colors cursor-pointer')

    with ui.column().classes('h-screen overflow-hidden flex-1 flex flex-col bg-background w-full p-0 m-0'):
        with ui.column().classes('flex-1 overflow-y-auto p-margin mt-16 pb-32 w-full max-w-7xl mx-auto'):
            
            # Action Bar specific to this telescope
            with ui.row().classes('w-full flex justify-between items-center mb-xl'):
                ui.label('Telemetry & Control').classes('font-headline-md text-headline-md font-bold border-l-4 border-primary pl-md')
                
                with ui.row().classes('gap-sm'):
                    resume_btn = ui.button('RESUME SCHEDULE', on_click=lambda: _resume_schedule(telescope_id)).classes('bg-secondary text-on-surface font-label-sm text-label-sm px-lg py-sm rounded-full shadow-lg hover:brightness-110 transition-all uppercase tracking-wider')
                    abort_btn = ui.button('ABORT', on_click=lambda: _trigger_abort(telescope_id)).classes('bg-error text-on-error font-label-sm text-label-sm px-lg py-sm rounded-full shadow-lg hover:bg-error-container hover:text-on-error-container transition-all uppercase tracking-wider')

            # Main Telemetry Panel
            with ui.element('div').classes('grid grid-cols-1 lg:grid-cols-3 gap-gutter w-full mb-xl'):
                
                # Big Coordinates
                with ui.column().classes('glass-panel panel-border rounded-xl p-xl flex flex-col justify-center lg:col-span-2'):
                    ui.label('Current Pointing').classes('text-label-lg font-label-lg text-on-surface-variant uppercase tracking-wider mb-lg')
                    
                    with ui.row().classes('w-full flex justify-around items-center'):
                        with ui.column().classes('items-center'):
                            ui.label('RA').classes('text-label-sm font-label-sm text-outline-variant mb-xs')
                            ra_label = ui.label('--h --m --s').classes('font-data-mono text-[2.5rem] text-primary font-light tracking-tight')
                        
                        with ui.column().classes('items-center'):
                            ui.label('DEC').classes('text-label-sm font-label-sm text-outline-variant mb-xs')
                            dec_label = ui.label('--° --\' --"').classes('font-data-mono text-[2.5rem] text-primary font-light tracking-tight')
                
                # State Indicators
                with ui.column().classes('glass-panel panel-border rounded-xl p-lg space-y-md'):
                    ui.label('Subsystem States').classes('text-label-md font-label-md text-on-surface-variant uppercase tracking-wider mb-sm')
                    
                    states = {}
                    for title in ['Mode', 'Mount', 'Dome', 'Skychart']:
                        with ui.row().classes('w-full flex justify-between items-center p-sm terminal-bg border border-outline-variant/30 rounded mt-2'):
                            ui.label(title).classes('text-label-sm text-on-surface-variant')
                            states[title] = ui.label('UNKNOWN').classes('font-data-mono text-secondary')

            # Active Target & Progress
            with ui.column().classes('glass-panel panel-border rounded-xl p-lg w-full mb-xl'):
                ui.label('Current Observation').classes('text-label-md font-label-md text-on-surface-variant uppercase tracking-wider mb-md block')
                
                target_container = ui.row().classes('w-full flex items-center justify-between p-md terminal-bg border border-primary/30 rounded')
                with target_container:
                    with ui.row().classes('flex items-center gap-md'):
                        target_icon = ui.icon('track_changes').classes('text-3xl text-primary')
                        with ui.column().classes('gap-0'):
                            target_name = ui.label('IDLE').classes('font-headline-sm text-headline-sm text-on-surface font-semibold')
                            proposal_name = ui.label('Waiting for schedule...').classes('text-label-sm font-label-sm text-on-surface-variant')
                            
                    with ui.column().classes('items-end gap-1 w-1/3'):
                        prog_text = ui.label('').classes('text-label-sm font-data-mono text-on-surface-variant')
                        prog_bar = ui.linear_progress(0.0, show_value=False, color='primary').classes('w-full h-2 rounded').style('display: none')
                        
            # Dynamic Telemetry Details grid
            extra_telemetry_container = ui.element('div').classes('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-sm w-full')
            
            # JSON Config Expansion Panel
            with ui.expansion('Observation Payload (JSON)', icon='data_object').classes('w-full mt-md glass-panel border border-outline-variant/30 rounded'):
                with ui.element('div').classes('w-full max-h-96 overflow-y-auto terminal-bg p-sm rounded'):
                    config_json = ui.code('', language='json').classes('text-xs w-full bg-transparent')
            
        # Terminal Footer
        log_components = render_log_console()

        def _trigger_abort(t_id):
            ui.notify(f"Aborting {t_id} and entering Manual Mode!", type='negative', position='top')
            orchestrator.abort_telescope(t_id, "Operator Aborted via Telescope Page")
            
        def _resume_schedule(t_id):
            ui.notify(f"Resuming Auto Schedule for {t_id}...", type='positive', position='top')
            executor = orchestrator.plugin_manager.get_telescope_plugin(t_id)
            if t_id in getattr(orchestrator, 'executors', {}):
                # The orchestrator uses executor_manager to store executors
                pass
            from core.executors.manager import executor_manager
            if t_id in executor_manager.executors:
                executor_manager.executors[t_id].is_manual_mode = False
                # If loop was dead, start it again
                if not executor_manager.executors[t_id]._running:
                    executor_manager.executors[t_id].start()

        def update_telescope_ui():
            status = orchestrator.get_system_status()
            executors = status.get('executors', {})
            t_exec = executors.get(telescope_id, {})
            
            if not t_exec:
                status_badge.set_text('OFFLINE').classes(replace='text-label-md font-label-md px-md py-1.5 glass-panel panel-border rounded-full tracking-wider uppercase text-error bg-error-container')
                return
                
            status_badge.set_text('ONLINE').classes(replace='text-label-md font-label-md px-md py-1.5 glass-panel panel-border rounded-full tracking-wider uppercase text-secondary bg-secondary-container/20')
            
            is_manual = t_exec.get('is_manual_mode', False)
            raw_state = t_exec.get('current_state', 'IDLE')
            is_running = t_exec.get('running', False)
            
            # Action Buttons
            if is_manual:
                resume_btn.enable()
                abort_btn.disable()
            else:
                resume_btn.disable()
                abort_btn.enable()
            
            # RA/DEC
            current_ra = t_exec.get('current_ra')
            current_dec = t_exec.get('current_dec')
            if current_ra is not None:
                ra_label.set_text(format_ra(current_ra))
            if current_dec is not None:
                dec_label.set_text(format_dec(current_dec))
                
            # States
            states['Mode'].set_text('MANUAL' if is_manual else 'AUTO').classes(replace=f"font-data-mono {'text-tertiary font-bold' if is_manual else 'text-secondary'}")
            
            mount_status = raw_state
            if raw_state in ['CONFIGURING', 'EXPOSING', 'READING_OUT']:
                mount_status = 'TRACKING'
            elif raw_state == 'DONE':
                mount_status = 'IDLE'
            
            states['Mount'].set_text(mount_status).classes(replace=f"font-data-mono {'text-tertiary' if mount_status == 'SLEWING' else 'text-primary'}")
            
            # Additional keys from telemetry
            dome_status = t_exec.get('dome_status', True)
            skychart = t_exec.get('skychart_online', True)
            
            states['Dome'].set_text('OPEN' if dome_status else 'CLOSED').classes(replace=f"font-data-mono {'text-secondary' if dome_status else 'text-error'}")
            states['Skychart'].set_text('ONLINE' if skychart else 'OFFLINE').classes(replace=f"font-data-mono {'text-secondary' if skychart else 'text-error'}")

            # Active Target & Progress
            current_obs = t_exec.get('current_obs_id')
            current_obs_dict = t_exec.get('current_obs_dict')
            if current_obs and raw_state != 'IDLE':
                target_name.set_text(current_obs)
                proposal_name.set_text("Active Observation")
                target_icon.classes(replace='text-3xl text-primary animate-pulse')
                if current_obs_dict:
                    config_json.set_content(json.dumps(current_obs_dict, indent=2))
            else:
                target_name.set_text('IDLE')
                proposal_name.set_text('Waiting for schedule...' if not is_manual else 'Manual control enabled')
                target_icon.classes(replace='text-3xl text-outline-variant')
                prog_bar.style('display: none')
                prog_text.set_text('')
                config_json.set_content('{}')
                
            import time
            exp_start = t_exec.get('exposure_start_time')
            exp_dur = t_exec.get('exposure_duration')
            if raw_state == 'EXPOSING' and exp_start is not None and exp_dur is not None:
                elapsed = time.time() - exp_start
                progress = min(max(elapsed / exp_dur, 0.0), 1.0) if exp_dur > 0 else 1.0
                prog_bar.set_value(progress)
                prog_bar.style('display: block')
                prog_text.set_text(f'{elapsed:.1f}s / {exp_dur}s')
            elif raw_state != 'EXPOSING':
                prog_bar.style('display: none')
                prog_text.set_text('')
                
            # Extra Telemetry details
            keys_to_exclude = {
                "telescope_id", "running", "queue_size", "current_obs_id", 
                "current_state", "current_ra", "current_dec", "exposure_start_time", 
                "exposure_duration", "ra", "dec", "is_manual_mode", "dome_status", "skychart_online",
                "connected", "current_obs_dict"
            }
            
            extra_items = []
            for k, v in t_exec.items():
                if k in keys_to_exclude:
                    continue
                title = k.replace('_', ' ').title()
                extra_items.append((title, v))
                
            current_extra_str = str(sorted(extra_items, key=lambda x: x[0]))
            last_extra_str = getattr(extra_telemetry_container, '_last_rendered_state', None)
            
            if current_extra_str != last_extra_str:
                extra_telemetry_container.clear()
                with extra_telemetry_container:
                    for title, val in extra_items:
                        with ui.column().classes('glass-panel p-sm rounded border border-outline-variant/30'):
                            ui.label(title).classes('text-[10px] uppercase text-on-surface-variant font-bold tracking-wider mb-1')
                            if isinstance(val, bool):
                                ui.label('YES' if val else 'NO').classes(f"font-data-mono text-sm {'text-secondary' if val else 'text-on-surface-variant'}")
                            elif isinstance(val, (int, float)):
                                ui.label(f"{val:.2f}").classes('font-data-mono text-sm text-primary')
                            else:
                                ui.label(str(val)).classes('font-data-mono text-sm text-on-surface')
                extra_telemetry_container._last_rendered_state = current_extra_str

            # Update Log Console
            update_log_console(log_components, status)

        # Update loop
        ui.timer(0.1, update_telescope_ui)

@ui.page('/telescope/{telescope_id}')
def telescope_page(telescope_id: str):
    build_telescope_page(telescope_id)
