from nicegui import ui
import datetime

def render_log_console():
    container_classes = 'fixed bottom-0 right-0 left-0 terminal-bg border-t border-outline-variant z-40 overflow-hidden flex flex-col p-0 gap-0 transition-all duration-300'
    
    # Wrap in a column that holds the state
    main_column = ui.column().classes(f'{container_classes} h-32')
    
    with main_column:
        with ui.row().classes('flex w-full items-center justify-between px-md py-1 bg-surface-container-low border-b border-outline-variant m-0'):
            with ui.row().classes('flex items-center gap-sm'):
                ui.icon('list').classes('text-sm text-on-surface-variant')
                ui.label('Live Event Log').classes('text-label-sm font-label-sm uppercase tracking-widest text-on-surface-variant')
            with ui.row().classes('flex gap-md items-center'):
                ui.label('CONNECTED: 127.0.0.1').classes('text-[10px] text-on-surface-variant')
                time_label = ui.label('').classes('text-[10px] text-primary')
                ui.timer(1.0, lambda: time_label.set_text(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')))
                
                # Height toggles
                def set_height(h):
                    main_column.classes(replace=f'{container_classes} {h}')
                    
                with ui.row().classes('flex gap-1 ml-4'):
                    ui.icon('minimize').classes('cursor-pointer hover:text-primary text-on-surface-variant text-sm').on('click', lambda: set_height('h-12'))
                    ui.icon('unfold_more').classes('cursor-pointer hover:text-primary text-on-surface-variant text-sm').on('click', lambda: set_height('h-64'))
                    ui.icon('fullscreen').classes('cursor-pointer hover:text-primary text-on-surface-variant text-sm').on('click', lambda: set_height('h-[calc(100vh-72px)]'))
                    ui.icon('close_fullscreen').classes('cursor-pointer hover:text-primary text-on-surface-variant text-sm').on('click', lambda: set_height('h-32'))
                
        log_container = ui.scroll_area().classes('flex-1 w-full overflow-y-auto p-sm font-data-mono text-data-mono scrollbar-hide text-on-surface-variant')
        with log_container:
            log_content = ui.html().classes('w-full')
            
    return {'container': log_container, 'content': log_content}

def update_log_console(components, status):
    logs = status.get('recent_logs', [])
    content = components['content']
    
    html_lines = []
    for log in logs[-50:]:
        parts = log.split(' - ', 1)
        if len(parts) == 2:
            meta = parts[0].replace('[', '')
            msg = parts[1]
            
            meta_parts = meta.split('] ')
            if len(meta_parts) == 2:
                ts = meta_parts[0]
                lvl = meta_parts[1]
                html_lines.append(
                    f'<div class="flex gap-md mb-base w-full items-start">'
                    f'<span class="text-primary w-40 shrink-0">{ts} | {lvl}</span>'
                    f'<span class="flex-1">| {msg}</span>'
                    f'</div>'
                )
                continue
                
        html_lines.append(f'<div class="flex gap-md mb-base w-full"><span class="flex-1">{log}</span></div>')
        
    content.set_content(''.join(html_lines))
