from nicegui import ui

def render_status_cards():
    components = {}
    with ui.column().classes('glass-panel panel-border rounded-xl p-md flex flex-col justify-center'):
        ui.label('Active Telescopes').classes('text-label-md font-label-md text-on-surface-variant uppercase tracking-widest block mb-xs')
        components['tel_label'] = ui.label('Loading...').classes('text-display-lg font-display-lg text-primary')
        
    with ui.column().classes('glass-panel panel-border rounded-xl p-md flex flex-col justify-center'):
        ui.label('Active Instruments').classes('text-label-md font-label-md text-on-surface-variant uppercase tracking-widest block mb-xs')
        components['inst_label'] = ui.label('Loading...').classes('text-display-lg font-display-lg text-primary')
        
    return components
