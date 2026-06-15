from nicegui import ui

def render_action_bar(orchestrator):
    with ui.column().classes('lg:col-span-2 glass-panel panel-border rounded-xl p-md flex flex-row items-center justify-between'):
        with ui.row().classes('flex items-center gap-md'):
            with ui.row().classes('bg-error-container/20 p-sm rounded-lg'):
                ui.icon('warning').classes('text-error').style("font-variation-settings: 'FILL' 1;")
            with ui.column().classes('gap-0'):
                ui.label('Manual Override').classes('font-label-md text-label-md text-on-surface-variant uppercase tracking-widest')
                ui.label('Standby Mode').classes('text-on-surface font-headline-sm')
                
        with ui.row().classes('flex items-center gap-sm'):
            def toggle_mode(e):
                orchestrator.set_operating_mode(e.value)
                if e.value:
                    ui.notify('System switched to MANUAL mode.', type='warning')
                else:
                    ui.notify('System switched to AUTO mode.', type='info')
            ui.switch('', on_change=toggle_mode).classes('text-primary')
            
            def do_sync():
                orchestrator.sync_now()
                ui.notify('Schedule Sync Triggered!', type='positive')
            ui.button('FORCE SYNC', icon='sync', on_click=do_sync).classes('bg-primary text-on-primary px-md py-sm rounded-lg font-label-md text-label-md hover:brightness-110 transition-all flex items-center gap-sm shadow-none')
