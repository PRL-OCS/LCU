from nicegui import ui
import asyncio
from core.orchestrator import orchestrator

from components.action_bar import render_action_bar
from components.status_cards import render_status_cards
from components.hardware_grid import render_hardware_grid, update_hardware_grid
from components.log_console import render_log_console, update_log_console

@ui.page('/')
def dashboard_page():
    ui.add_head_html(open('stitch_theme.html').read())
    ui.dark_mode().enable()
    ui.colors(primary='#a7caec', secondary='#b5ccc1', accent='#ebbf8e', dark='#111318', positive='#b5ccc1', negative='#ffb4ab', warning='#ebbf8e', info='#a7caec')
    
    # TopAppBar (Must be direct child of page)
    with ui.header().classes('bg-surface-container fixed top-0 w-full z-50 border-b border-outline-variant flex justify-between items-center px-md h-16 transition-colors duration-200 ease-in-out'):
        with ui.row().classes('flex items-center gap-md'):
            ui.icon('menu').classes('md:hidden p-base text-primary')
            ui.label('LCU').classes('font-headline-sm text-headline-sm font-semibold text-on-surface')
        with ui.row().classes('flex items-center gap-md'):
            with ui.row().classes('hidden lg:flex items-center gap-sm px-md py-1.5 glass-panel panel-border rounded-full'):
                ui.label('').classes('w-2 h-2 rounded-full bg-[#10B981] animate-pulse')
                ui.label('System Optimal').classes('text-label-md font-label-md text-on-surface-variant uppercase tracking-wider')
            ui.icon('settings').classes('p-base text-on-surface-variant hover:bg-surface-container-highest transition-colors cursor-pointer')

    with ui.column().classes('h-screen overflow-hidden flex-1 flex flex-col bg-background w-full p-0 m-0'):
        # Content Area
        with ui.column().classes('flex-1 overflow-y-auto p-margin mt-16 pb-32 w-full max-w-7xl mx-auto'):
            # Manual Override & Quick Stats
            with ui.element('div').classes('grid grid-cols-1 lg:grid-cols-4 gap-gutter mb-xl w-full'):
                render_action_bar(orchestrator)
                status_components = render_status_cards()
                
            # Hardware State Headline
            with ui.row().classes('flex items-center gap-md mb-md w-full'):
                ui.label('Hardware State').classes('font-headline-sm text-headline-sm font-semibold border-l-4 border-primary pl-md')
                ui.element('div').classes('flex-1 h-[1px] bg-outline-variant')
            
            # Hardware Grid
            hardware_container = render_hardware_grid()
            
        # Terminal Footer
        log_components = render_log_console()

        def update_ui():
            status = orchestrator.get_system_status()
            
            # Update Top Cards
            status_components['tel_label'].set_text(str(len(status.get('telescope_plugins', {}))))
            status_components['inst_label'].set_text(str(len(status.get('instrument_plugins', {}))))
            
            # Update Hardware Grid
            update_hardware_grid(hardware_container, status)

            # Update Log Console
            update_log_console(log_components, status)

        # Run update loop every 0.1 seconds for ultra-smooth progress bars
        ui.timer(0.1, update_ui)
