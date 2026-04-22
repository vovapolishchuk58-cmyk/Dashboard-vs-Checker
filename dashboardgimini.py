# dashboardgimini.py (UI-only) - DARK MODE ENABLED - FIXED VERSION
# ------------------------------------------------------------
# ✅ ВИПРАВЛЕННЯ:
# - Використання Supabase для зберігання даних
# - Видалено дубльовані функції нормалізації та I/O
# - Видалено застарілий локальний механізм блокування файлів
# ------------------------------------------------------------

import os
import ast
import json
import traceback
from datetime import datetime
from io import StringIO
import asyncio
import logging

import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate

logger = logging.getLogger(__name__)

from product_data import (
    normalize_product_defaults,
    load_products,
    save_products,
    update_products_locked, # Added
    delete_product_by_url,
)
from checker import get_product_data_async, format_price_text # Added

# =========================================================================
# 1. DataFrame Helper
# =========================================================================

def products_to_dataframe(products_list: list) -> pd.DataFrame:
    rows = []
    for p in products_list:
        p = normalize_product_defaults(p)
        image_url = p.get('image_current') or p.get('manual_image_url')

        rows.append({
            'supplier': p.get('supplier', 'Не вказано'),
            'product_name': p.get('product_name', '—'),
            'availability_text': p.get('availability_text', '—'),
            'availability_code': p.get('availability_code', 'UNKNOWN'),
            'price_text': p.get('price_text', '—'),
            'price_current': p.get('price_current', None),
            'image_current': image_url,
            'category': p.get('category', 'Не вказано'),
            'color': p.get('color', '—'),
            'url': p.get('url'),
            'last_checked_iso': p.get('last_checked_iso') or p.get('last_checked') or None,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=[
            'supplier', 'product_name', 'availability_text', 'availability_code',
            'price_text', 'price_current', 'image_current',
            'category', 'color', 'url', 'last_checked_iso'
        ])

    if 'last_checked_iso' in df.columns:
        df['_last_checked_dt'] = pd.to_datetime(df['last_checked_iso'], errors='coerce')
        df = df.sort_values(by='_last_checked_dt', ascending=False, na_position='last')
        df = df.drop(columns=['_last_checked_dt'])

    return df


def safe_get_triggered_url(ctx, callback_name: str = "callback") -> str:
    if not ctx.triggered:
        raise PreventUpdate

    triggered_id = ctx.triggered_id
    if isinstance(triggered_id, dict):
        return triggered_id.get('url')

    if isinstance(triggered_id, str):
        try:
            parsed = json.loads(triggered_id)
            if isinstance(parsed, dict):
                return parsed.get('url')
        except Exception:
            pass

    raise PreventUpdate


# =========================================================================
# 2. СУЧАСНІ СТИЛІ (CSS VARIABLES)
# =========================================================================

BASE_STYLE = {
    'fontFamily': "'Inter', sans-serif",
    'fontSize': '14px',
    'lineHeight': '1.6',
    'color': 'var(--text-main)',
    'backgroundColor': 'var(--bg-main)',
    'transition': 'background-color 0.3s ease, color 0.3s ease'
}

CONTAINER_STYLE = {
    **BASE_STYLE,
    'maxWidth': '1400px',
    'margin': '0 auto',
    'padding': '20px',
    'minHeight': '100vh',
}

HEADER_STYLE = {
    'background': 'var(--primary-gradient)',
    'color': '#ffffff',
    'padding': '20px 30px',
    'borderRadius': '16px',
    'display': 'flex',
    'justifyContent': 'space-between',
    'alignItems': 'center',
    'marginBottom': '30px',
    'boxShadow': 'var(--shadow-lg)',
}

FORM_CARD_STYLE = {
    'backgroundColor': 'var(--bg-card)',
    'borderRadius': '16px',
    'padding': '25px',
    'marginBottom': '25px',
    'boxShadow': 'var(--shadow)',
    'border': '1px solid var(--border)',
    'transition': 'all 0.3s ease',
}

INPUT_STYLE = {
    'width': '100%',
    'padding': '10px 14px',
    'fontSize': '14px',
    'border': '2px solid var(--border)',
    'borderRadius': '10px',
    'boxSizing': 'border-box',
    'outline': 'none',
    'backgroundColor': 'var(--input-bg)',
    'color': 'var(--text-main)',
    'transition': 'all 0.2s ease',
}

BUTTON_PRIMARY_STYLE = {
    'padding': '10px 20px',
    'fontSize': '14px',
    'fontWeight': '600',
    'color': '#ffffff',
    'background': 'var(--primary-gradient)',
    'border': 'none',
    'borderRadius': '10px',
    'cursor': 'pointer',
    'transition': 'all 0.3s ease',
    'boxShadow': '0 4px 12px rgba(99, 102, 241, 0.3)',
}

BUTTON_SUCCESS_STYLE = {
    **BUTTON_PRIMARY_STYLE,
    'background': 'var(--success)',
    'boxShadow': 'none',
}

TABLE_STYLE = {
    'width': '100%',
    'borderCollapse': 'separate',
    'borderSpacing': '0',
    'backgroundColor': 'var(--bg-card)',
    'borderRadius': '12px',
    'overflow': 'hidden',
    'boxShadow': 'var(--shadow)',
    'color': 'var(--text-main)',
}

TABLE_HEADER_STYLE = {
    'background': 'var(--bg-header)',
    'color': 'var(--text-sub)',
    'padding': '16px',
    'fontWeight': '600',
    'fontSize': '12px',
    'textTransform': 'uppercase',
    'letterSpacing': '0.5px',
    'textAlign': 'left',
    'borderBottom': '2px solid var(--border)',
}

TABLE_CELL_STYLE = {
    'padding': '16px',
    'borderBottom': '1px solid var(--border)',
    'fontSize': '14px',
    'verticalAlign': 'middle',
}

MODAL_OVERLAY_STYLE = {
    'position': 'fixed',
    'top': '0',
    'left': '0',
    'width': '100%',
    'height': '100%',
    'backgroundColor': 'rgba(0, 0, 0, 0.6)',
    'backdropFilter': 'blur(4px)',
    'display': 'flex',
    'justifyContent': 'center',
    'alignItems': 'center',
    'zIndex': '1000',
}

MODAL_CONTENT_STYLE = {
    'backgroundColor': 'var(--bg-card)',
    'color': 'var(--text-main)',
    'borderRadius': '16px',
    'padding': '30px',
    'width': '90%',
    'maxWidth': '700px',
    'maxHeight': '90vh',
    'overflowY': 'auto',
    'boxShadow': 'var(--shadow-lg)',
    'border': '1px solid var(--border)',
}


def get_status_badge_style(code: str) -> dict:
    code = (code or 'UNKNOWN').upper()
    base = {
        'display': 'inline-block',
        'padding': '6px 12px',
        'borderRadius': '20px',
        'fontSize': '12px',
        'fontWeight': '600',
        'textTransform': 'uppercase',
        'letterSpacing': '0.5px',
    }

    if code == 'AVAILABLE':
        return {**base, 'backgroundColor': 'var(--success-bg)', 'color': 'var(--success-text)'}
    elif code == 'OUT_OF_STOCK':
        return {**base, 'backgroundColor': 'var(--danger-bg)', 'color': 'var(--danger-text)'}
    elif code == 'ERROR':
        return {**base, 'backgroundColor': 'var(--warning-bg)', 'color': 'var(--warning-text)'}
    else:
        return {**base, 'backgroundColor': 'var(--info-bg)', 'color': 'var(--info-text)'}


def get_row_style_by_code(code: str) -> dict:
    # currently not used for conditional row coloring; kept for future
    return {'backgroundColor': 'var(--bg-card)'}



# =========================================================================
# 3. DASH ІНТЕРФЕЙС
# =========================================================================

app = dash.Dash(__name__, prevent_initial_callbacks='initial_duplicate')
server = app.server
app.title = "🛍️ Моніторинг товарів v3"

# --- CSS зі змінними ---
app.index_string = '''
<!DOCTYPE html>
<html lang="uk">
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                /* Light Theme */
                --bg-main: #f3f4f6;
                --bg-card: #ffffff;
                --bg-header: #f9fafb;
                
                --text-main: #1f2937;
                --text-sub: #6b7280;
                
                --border: #e5e7eb;
                --input-bg: #ffffff;
                
                --primary-gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
                
                --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                
                /* Status Colors (Light) */
                --success: #10b981;
                --success-bg: #d1fae5;
                --success-text: #065f46;
                
                --danger: #ef4444;
                --danger-bg: #fee2e2;
                --danger-text: #991b1b;
                
                --warning: #f59e0b;
                --warning-bg: #fef3c7;
                --warning-text: #92400e;
                
                --info: #3b82f6;
                --info-bg: #dbeafe;
                --info-text: #1e40af;
            }

            [data-theme="dark"] {
                /* Dark Theme */
                --bg-main: #111827;
                --bg-card: #1f2937;
                --bg-header: #374151;
                
                --text-main: #f9fafb;
                --text-sub: #9ca3af;
                
                --border: #374151;
                --input-bg: #111827;
                
                --primary-gradient: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                
                --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
                --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
                
                /* Status Colors (Dark - dimmer backgrounds, lighter text) */
                --success: #34d399;
                --success-bg: rgba(6, 95, 70, 0.5);
                --success-text: #d1fae5;
                
                --danger: #f87171;
                --danger-bg: rgba(127, 29, 29, 0.5);
                --danger-text: #fee2e2;
                
                --warning: #fbbf24;
                --warning-bg: rgba(120, 53, 15, 0.5);
                --warning-text: #fef3c7;
                
                --info: #60a5fa;
                --info-bg: rgba(30, 58, 138, 0.5);
                --info-text: #dbeafe;
            }

            body {
                background-color: var(--bg-main);
                color: var(--text-main);
                margin: 0;
                transition: background-color 0.3s ease, color 0.3s ease;
            }
            
            /* Custom Scrollbar */
            ::-webkit-scrollbar {
                width: 10px;
                height: 10px;
            }
            ::-webkit-scrollbar-track {
                background: var(--bg-main); 
            }
            ::-webkit-scrollbar-thumb {
                background: var(--text-sub); 
                border-radius: 5px;
                opacity: 0.5;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: var(--text-main); 
            }

            /* Animations */
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .animate-fade-in {
                animation: fadeIn 0.4s ease-out forwards;
            }

            /* Dropdown overrides for Dark Mode */
            .Select-control {
                background-color: var(--input-bg) !important;
                border-color: var(--border) !important;
                color: var(--text-main) !important;
            }
            .Select-placeholder, .Select-value-label, .Select-input > input {
                color: var(--text-main) !important;
            }
            .Select-menu-outer {
                background-color: var(--bg-card) !important;
                border: 1px solid var(--border) !important;
                color: var(--text-main) !important;
            }
            .Select-option {
                background-color: var(--bg-card) !important;
                color: var(--text-main) !important;
            }
            .Select-option.is-focused {
                background-color: var(--border) !important;
            }
            
            /* Inputs */
            input:focus, select:focus {
                border-color: #6366f1 !important;
                box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
            }
            
            /* Buttons */
            button:hover {
                transform: translateY(-1px);
                filter: brightness(110%);
            }
            button:active {
                transform: translateY(0);
            }

            /* Theme Toggle */
            .theme-toggle-btn {
                background: rgba(255, 255, 255, 0.2);
                border: none;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
                color: white;
                transition: all 0.3s ease;
            }
            .theme-toggle-btn:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: rotate(15deg);
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# --- Layout ---
app.layout = html.Div(style=CONTAINER_STYLE, children=[

    dcc.Store(id='data-refresh-trigger', data=0),
    dcc.Store(id='edit-item-url', data=None),
    dcc.Store(id='products-snapshot', data={'timestamp': None, 'df_json': None}),

    # Theme Store & Client-side logic will be handled via callback
    dcc.Store(id='theme-store', storage_type='local', data='light'),

    # Header
    html.Div(style=HEADER_STYLE, children=[
        html.Div([
            html.H1("🛍️ Моніторинг товарів v3", style={'margin': 0, 'fontSize': '24px', 'fontWeight': '700'}),
            html.Span("Контроль цін та наявності", style={'fontSize': '13px', 'opacity': 0.8, 'display': 'block', 'marginTop': '4px'})
        ]),
        html.Button('🌙', id='theme-toggle-btn', className='theme-toggle-btn', title="Змінити тему")
    ]),

    # --- Форма "Додати новий товар" ---
    html.Details([
        html.Summary('➕ Додати новий товар', style={
            'cursor': 'pointer',
            'fontSize': '16px',
            'fontWeight': '600',
            'margin': '0 0 15px 0',
            'padding': '15px',
            'backgroundColor': 'var(--bg-card)',
            'borderRadius': '12px',
            'boxShadow': 'var(--shadow)',
            'color': 'var(--text-main)',
            'listStyle': 'none'
        }),
        html.Div([
            html.Div(style={'display': 'flex', 'gap': '15px', 'marginBottom': '15px', 'flexWrap': 'wrap'}, children=[
                html.Div(style={'flex': '2 1 300px'}, children=[
                    html.Label('Назва товару *', style={'display': 'block', 'marginBottom': '6px', 'fontWeight': '600', 'fontSize': '13px', 'color': 'var(--text-sub)'}),
                    dcc.Input(id='input-product-name', type='text', placeholder='Введіть назву товару', style=INPUT_STYLE),
                ]),

                html.Div(style={'flex': '1 1 120px'}, children=[
                    html.Label('Колір', style={'display': 'block', 'marginBottom': '6px', 'fontWeight': '600', 'fontSize': '13px', 'color': 'var(--text-sub)'}),
                    dcc.Input(id='input-color', type='text', placeholder='Колір', list='color-datalist', style=INPUT_STYLE),
                    html.Datalist(id='color-datalist')
                ]),

                html.Div(style={'flex': '1 1 180px'}, children=[
                    html.Label('Постачальник', style={'display': 'block', 'marginBottom': '6px', 'fontWeight': '600', 'fontSize': '13px', 'color': 'var(--text-sub)'}),
                    dcc.Input(id='input-supplier', type='text', placeholder='Постачальник', list='supplier-datalist', style=INPUT_STYLE),
                    html.Datalist(id='supplier-datalist')
                ]),

                html.Div(style={'flex': '1 1 180px'}, children=[
                    html.Label('Категорія', style={'display': 'block', 'marginBottom': '6px', 'fontWeight': '600', 'fontSize': '13px', 'color': 'var(--text-sub)'}),
                    dcc.Input(id='input-category', type='text', placeholder='Категорія', list='category-datalist', style=INPUT_STYLE),
                    html.Datalist(id='category-datalist')
                ]),
            ]),

            html.Div(style={'marginBottom': '15px'}, children=[
                html.Label('URL товару *', style={'display': 'block', 'marginBottom': '6px', 'fontWeight': '600', 'fontSize': '13px', 'color': 'var(--text-sub)'}),
                dcc.Input(id='input-url', type='text', placeholder="https://example.com/product", style=INPUT_STYLE),
            ]),

            html.Hr(style={'margin': '20px 0', 'border': 'none', 'borderTop': '1px solid var(--border)'}),

            html.Label("🔍 CSS-селектори:", style={'fontWeight': '600', 'marginBottom': '12px', 'display': 'block', 'fontSize': '14px'}),

            html.Div(style={'display': 'flex', 'gap': '15px', 'marginBottom': '15px', 'flexWrap': 'wrap'}, children=[
                html.Div(style={'flex': '1 1 250px'}, children=[
                    html.Label('Селектор наявності', style={'display': 'block', 'marginBottom': '6px', 'fontSize': '12px', 'color': 'var(--text-sub)'}),
                    dcc.Input(id='input-sel-availability', type='text', placeholder='.availability-status', style=INPUT_STYLE),
                ]),
                html.Div(style={'flex': '1 1 250px'}, children=[
                    html.Label('Селектор ціни (РРЦ)', style={'display': 'block', 'marginBottom': '6px', 'fontSize': '12px', 'color': 'var(--text-sub)'}),
                    dcc.Input(id='input-sel-rrp', type='text', placeholder='.price-value', style=INPUT_STYLE),
                ]),
                html.Div(style={'flex': '1 1 250px'}, children=[
                    html.Label('Селектор ВІДСУТНОСТІ', style={'display': 'block', 'marginBottom': '6px', 'fontSize': '12px', 'color': 'var(--text-sub)'}),
                    dcc.Input(id='input-sel-out-of-stock', type='text', placeholder='.sold-out-badge', style=INPUT_STYLE),
                ]),
            ]),

            html.Div(style={'marginBottom': '20px'}, children=[
                html.Label('🖼️ Або вкажіть URL фото вручну:', style={'display': 'block', 'marginBottom': '6px', 'fontSize': '12px', 'color': 'var(--text-sub)'}),
                dcc.Input(id='input-manual-image', type='url', placeholder='https://example.com/image.jpg', style=INPUT_STYLE),
            ]),

            html.Button('✅ Додати товар', id='add-product-button', n_clicks=0, style=BUTTON_SUCCESS_STYLE),

        ], style=FORM_CARD_STYLE)
    ], style={'marginBottom': '25px'}),

    html.Div(id='action-output-message', style={'margin': '15px 0', 'fontWeight': '600', 'fontSize': '14px'}),

    # --- Фільтри ---
    html.Div(style=FORM_CARD_STYLE, children=[
        html.Div([
            html.Label('🔍 Швидкий пошук', style={'display': 'block', 'marginBottom': '8px', 'fontWeight': '600', 'fontSize': '14px'}),
            dcc.Input(
                id='product-search-input',
                type='text',
                placeholder='Назва, постачальник, категорія...',
                style={**INPUT_STYLE, 'fontSize': '15px'}
            ),
        ], style={'marginBottom': '20px'}),

        html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(auto-fit, minmax(200px, 1fr))', 'gap': '15px'}, children=[
            html.Div([
                html.Label("Постачальник", style={'marginBottom': '8px', 'fontWeight': '600', 'display': 'block', 'fontSize': '13px'}),
                dcc.Dropdown(
                    id='supplier-filter',
                    options=[],
                    placeholder="Всі",
                    multi=True,
                )
            ]),

            html.Div([
                html.Label("Категорія", style={'marginBottom': '8px', 'fontWeight': '600', 'display': 'block', 'fontSize': '13px'}),
                dcc.Dropdown(
                    id='category-filter',
                    options=[],
                    placeholder="Всі",
                    multi=True,
                )
            ]),

            html.Div([
                html.Label("Статус", style={'marginBottom': '8px', 'fontWeight': '600', 'display': 'block', 'fontSize': '13px'}),
                dcc.Dropdown(
                    id='availability-filter',
                    options=[
                        {'label': '✅ В наявності', 'value': 'AVAILABLE'},
                        {'label': '❌ Немає', 'value': 'OUT_OF_STOCK'},
                        {'label': '⚠️ Помилка', 'value': 'ERROR'},
                        {'label': '❔ Невідомо', 'value': 'UNKNOWN'},
                    ],
                    placeholder="Всі",
                    multi=True,
                )
            ]),
        ]),
    ]),

    # Автообновление
    dcc.Interval(id='interval-component', interval=300 * 1000, n_intervals=0),

    # Статус панель
    html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '20px', 'marginTop': '25px', 'padding': '0 10px'}, children=[
        html.Div(id='live-update-text', style={'fontWeight': '600', 'color': 'var(--text-sub)'}),
        html.Button('🔄 Оновити дані', id='refresh-button', n_clicks=0, style={
            **BUTTON_PRIMARY_STYLE,
            'padding': '10px 20px',
        })
    ]),

    html.Div(id='dashboard-table', className='animate-fade-in'),

    # --- Модальне вікно редагування ---
    html.Div(
        id='edit-modal-wrapper',
        style={**MODAL_OVERLAY_STYLE, 'display': 'none'},
        children=[
            html.Div(
                id='edit-modal-content',
                style=MODAL_CONTENT_STYLE,
                children=[
                    html.H2('✏️ Редагувати товар', style={'marginBottom': '20px', 'marginTop': '0'}),

                    html.Div(style={'display': 'flex', 'gap': '15px', 'marginBottom': '15px', 'flexWrap': 'wrap'}, children=[
                        html.Div(style={'flex': '2 1 200px'}, children=[
                            html.Label('Назва товару', style={'fontSize': '12px', 'fontWeight': '600', 'display': 'block', 'marginBottom': '6px', 'color': 'var(--text-sub)'}),
                            dcc.Input(id='edit-product-name', type='text', style=INPUT_STYLE),
                        ]),
                        html.Div(style={'flex': '1 1 100px'}, children=[
                            html.Label('Колір', style={'fontSize': '12px', 'fontWeight': '600', 'display': 'block', 'marginBottom': '6px', 'color': 'var(--text-sub)'}),
                            dcc.Input(id='edit-color', type='text', style=INPUT_STYLE),
                        ]),
                    ]),

                    html.Div(style={'display': 'flex', 'gap': '15px', 'marginBottom': '15px', 'flexWrap': 'wrap'}, children=[
                        html.Div(style={'flex': '1 1 200px'}, children=[
                            html.Label('Постачальник', style={'fontSize': '12px', 'fontWeight': '600', 'display': 'block', 'marginBottom': '6px', 'color': 'var(--text-sub)'}),
                            dcc.Input(id='edit-supplier', type='text', style=INPUT_STYLE),
                        ]),
                        html.Div(style={'flex': '1 1 200px'}, children=[
                            html.Label('Категорія', style={'fontSize': '12px', 'fontWeight': '600', 'display': 'block', 'marginBottom': '6px', 'color': 'var(--text-sub)'}),
                            dcc.Input(id='edit-category', type='text', style=INPUT_STYLE),
                        ]),
                    ]),

                    html.Div(style={'marginBottom': '15px'}, children=[
                        html.Label('URL (ID)', style={'fontSize': '12px', 'fontWeight': '600', 'display': 'block', 'marginBottom': '6px', 'color': 'var(--text-sub)'}),
                        dcc.Input(
                            id='edit-url',
                            type='text',
                            disabled=True,
                            style={**INPUT_STYLE, 'backgroundColor': 'var(--bg-main)', 'opacity': 0.7, 'cursor': 'not-allowed'}
                        ),
                    ]),

                    html.Hr(style={'margin': '20px 0', 'border': 'none', 'borderTop': '1px solid var(--border)'}),

                    html.P('🔍 Налаштування парсингу:', style={'fontWeight': '600', 'marginBottom': '12px'}),

                    html.Div(style={'display': 'flex', 'gap': '15px', 'marginBottom': '15px', 'flexWrap': 'wrap'}, children=[
                        html.Div(style={'flex': '1 1 200px'}, children=[
                            html.Label('CSS-селектор наявності', style={'fontSize': '12px', 'display': 'block', 'marginBottom': '6px', 'color': 'var(--text-sub)'}),
                            dcc.Input(id='edit-sel-availability', type='text', placeholder='.availability', style=INPUT_STYLE),
                        ]),
                        html.Div(style={'flex': '1 1 200px'}, children=[
                            html.Label('CSS-селектор РРЦ', style={'fontSize': '12px', 'display': 'block', 'marginBottom': '6px', 'color': 'var(--text-sub)'}),
                            dcc.Input(id='edit-sel-rrp', type='text', placeholder='.price', style=INPUT_STYLE),
                        ]),
                        html.Div(style={'flex': '1 1 200px'}, children=[
                            html.Label('Селектор ВІДСУТНОСТІ', style={'fontSize': '12px', 'display': 'block', 'marginBottom': '6px', 'color': 'var(--text-sub)'}),
                            dcc.Input(id='edit-sel-out-of-stock', type='text', placeholder='.sold-out', style=INPUT_STYLE),
                        ]),
                    ]),

                    html.Div(style={'marginBottom': '25px'}, children=[
                        html.Label('Вручну URL фото', style={'fontSize': '12px', 'display': 'block', 'marginBottom': '6px', 'color': 'var(--text-sub)'}),
                        dcc.Input(id='edit-manual-image', type='url', placeholder='https://...', style=INPUT_STYLE),
                    ]),

                    html.Div(style={'display': 'flex', 'gap': '12px', 'justifyContent': 'flex-end'}, children=[
                        html.Button('❌ Скасувати', id='cancel-edit-button', style={
                            'padding': '12px 24px',
                            'fontSize': '14px',
                            'fontWeight': '600',
                            'color': 'var(--text-main)',
                            'backgroundColor': 'transparent',
                            'border': '2px solid var(--border)',
                            'borderRadius': '10px',
                            'cursor': 'pointer',
                            'transition': 'all 0.3s ease',
                        }),
                        html.Button('💾 Зберегти зміни', id='save-edit-button', style=BUTTON_SUCCESS_STYLE),
                    ])
                ]
            )
        ]
    )
])

# =========================================================================
# CLIENT-SIDE CALLBACKS (THEME)
# =========================================================================

app.clientside_callback(
    """
    function(n_clicks, current_theme) {
        var new_theme = 'light';
        
        if (current_theme) {
            new_theme = current_theme;
        }
        
        if (n_clicks) {
            new_theme = (new_theme === 'light') ? 'dark' : 'light';
        }
        
        document.documentElement.setAttribute('data-theme', new_theme);
        
        var btn = document.getElementById('theme-toggle-btn');
        if(btn) {
            btn.textContent = (new_theme === 'dark') ? '☀️' : '🌙';
        }

        return new_theme;
    }
    """,
    Output('theme-store', 'data'),
    Input('theme-toggle-btn', 'n_clicks'),
    State('theme-store', 'data')
)

# =========================================================================
# 4. Callbacks
# =========================================================================

def format_datalist_options(values):
    unique_values = sorted(list(set(
        v.strip() for v in values
        if v and str(v).strip() not in ['—', 'не вказано', '', 'None', 'Не вказано']
    )))
    return [html.Option(value=v) for v in unique_values]


@app.callback(
    [Output('supplier-filter', 'options'),
     Output('supplier-datalist', 'children')],
    [Input('data-refresh-trigger', 'data'),
     Input('interval-component', 'n_intervals')]
)
def set_supplier_options(n_refresh, n_intervals):
    try:
        products_list = load_products()
        suppliers = [p.get('supplier') for p in products_list if p.get('supplier')]
        filter_options = [{'label': s, 'value': s} for s in sorted(list(set(suppliers)))]
        datalist_options = format_datalist_options(suppliers)
        return filter_options, datalist_options


    except Exception:
        return [], []


@app.callback(
    [Output('category-filter', 'options'),
     Output('category-datalist', 'children')],
    [Input('data-refresh-trigger', 'data'),
     Input('interval-component', 'n_intervals')]
)
def set_category_options(n_refresh, n_intervals):
    try:
        products_list = load_products()
        categories = [p.get('category') for p in products_list if p.get('category')]
        unique_categories = sorted(list(set(c.strip() for c in categories if c and c.strip())))
        filter_options = [{'label': c, 'value': c} for c in unique_categories]
        datalist_options = format_datalist_options(categories)
        return filter_options, datalist_options


    except Exception:
        return [], []


@app.callback(
    Output('color-datalist', 'children'),
    [Input('data-refresh-trigger', 'data'),
     Input('interval-component', 'n_intervals')]
)
def set_color_options(n_refresh, n_intervals):
    try:
        products_list = load_products()
        colors = [p.get('color') for p in products_list if p.get('color')]
        return format_datalist_options(colors)

    except TimeoutError:
        return []

    except Exception:
        return []


@app.callback(
    [Output('action-output-message', 'children', allow_duplicate=True),
     Output('data-refresh-trigger', 'data', allow_duplicate=True),
     Output('input-supplier', 'value'),
     Output('input-product-name', 'value'),
     Output('input-url', 'value'),
     Output('input-category', 'value'),
     Output('input-color', 'value'),
     Output('input-sel-availability', 'value'),
     Output('input-sel-rrp', 'value'),
     Output('input-sel-out-of-stock', 'value'),
     Output('input-manual-image', 'value')],
    [Input('add-product-button', 'n_clicks')],
    [State('input-supplier', 'value'),
     State('input-product-name', 'value'),
     State('input-url', 'value'),
     State('input-category', 'value'),
     State('input-color', 'value'),
     State('input-sel-availability', 'value'),
     State('input-sel-rrp', 'value'),
     State('input-sel-out-of-stock', 'value'),
     State('input-manual-image', 'value'),
     State('data-refresh-trigger', 'data')],
    prevent_initial_call=True
)
def add_new_product(n_clicks, supplier, product_name, url, category, color,
                    sel_avail, sel_rrp, sel_out_of_stock, manual_image, refresh_trigger):
    if not n_clicks:
        raise PreventUpdate

    empty_vals = [''] * 9

    if not url or not product_name:
        return (
            html.Span(
                "Назва та URL обов'язкові.",
                style={'color': 'var(--danger)', 'padding': '10px', 'backgroundColor': 'var(--danger-bg)', 'borderRadius': '8px', 'display': 'block'}
            ),
            dash.no_update,
            *empty_vals
        )

    try:
        products_list = load_products()

        if any(p.get('url') == url for p in products_list):
            return (
                html.Span(
                    "Товар з URL вже існує.",
                    style={'color': 'var(--danger)', 'padding': '10px', 'backgroundColor': 'var(--danger-bg)', 'borderRadius': '8px', 'display': 'block'}
                ),
                dash.no_update,
                *empty_vals
            )

        new_product = normalize_product_defaults({
            'supplier': supplier or 'Не вказано',
            'url': url,
            'product_name': product_name,
            'category': category.strip() if category else 'Не вказано',
            'color': color.strip() if color else '—',
            'selectors': {
                'availability': sel_avail or None,
                'rrp_price': sel_rrp or None,
                'out_of_stock': sel_out_of_stock or None,
                'image': None,
            },
            'manual_image_url': manual_image or None,
        })

        # Only upsert the new product to save time and avoid timeouts
        save_products([new_product])

        msg = html.Span(
            "✅ Товар додано.",
            style={'color': 'var(--success-text)', 'padding': '10px', 'backgroundColor': 'var(--success-bg)', 'borderRadius': '8px', 'display': 'block'}
        )
        return (msg, (refresh_trigger or 0) + 1, *empty_vals)

    except TimeoutError:
        # ✅ NEW: lock timeout -> user-friendly message
        return (warn_file_busy_span(), dash.no_update, *empty_vals)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Add product error: {error_details}")
        return (
            html.Div([
                html.Span(f"❌ Помилка: {str(e)}", style={'color': 'var(--danger)', 'fontWeight': 'bold'}),
                html.Pre(error_details, style={'fontSize': '10px', 'marginTop': '10px', 'whiteSpace': 'pre-wrap', 'color': 'var(--text-sub)'})
            ], style={'padding': '10px', 'backgroundColor': 'var(--danger-bg)', 'borderRadius': '8px'}),
            dash.no_update,
            *empty_vals
        )


@app.callback(
    [Output('products-snapshot', 'data'),
     Output('live-update-text', 'children', allow_duplicate=True)],
    [Input('interval-component', 'n_intervals'),
     Input('data-refresh-trigger', 'data'),
     Input('refresh-button', 'n_clicks')],
    prevent_initial_call=False
)
def load_snapshot_callback(n_intervals, n_trigger, n_clicks_refresh):
    try:
        products_list = load_products()
        df = products_to_dataframe(products_list)
        last_updated = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

        if df.empty:
            data_json = None
            update_text = f"🕒 Оновлено: {last_updated} | Товарів: 0"
        else:
            data_json = df.to_json(orient='split', date_format='iso')
            update_text = f"🕒 Оновлено: {last_updated} | Товарів: {len(df)}"

        return {'timestamp': last_updated, 'df_json': data_json}, update_text

    except TimeoutError:
        # ✅ NEW
        ts = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        return {'timestamp': ts, 'df_json': None}, "⏳ Файл даних зайнятий (йде оновлення). Спробуйте через 5–10 секунд."

    except Exception as e:
        logger.error(f"Snapshot load error: {e}")
        return {'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S'), 'df_json': None}, f"Error: {str(e)}"

@app.callback(
    [Output('dashboard-table', 'children'),
     Output('live-update-text', 'children', allow_duplicate=True)],
    [Input('products-snapshot', 'data'),
     Input('product-search-input', 'value'),
     Input('supplier-filter', 'value'),
     Input('category-filter', 'value'),
     Input('availability-filter', 'value')],
    prevent_initial_call=False
)
def filter_and_render_table(stored_data, search_term, selected_suppliers, selected_categories, selected_availability):
    try:
        if stored_data is None or stored_data.get('df_json') is None:
            ts = stored_data.get('timestamp') if stored_data else None
            msg = html.Div([
                html.Div('📦', style={'fontSize': '48px', 'marginBottom': '10px', 'opacity': 0.5}),
                html.H3('Список порожній', style={'color': 'var(--text-sub)', 'marginTop': 0}),
            ], style={'textAlign': 'center', 'padding': '40px', 'backgroundColor': 'var(--bg-card)', 'borderRadius': '12px', 'border': '1px dashed var(--border)'})
            return msg, f"🕒 Оновлено: {ts} | Товарів: 0"

        df_base = pd.read_json(StringIO(stored_data['df_json']), orient='split')
        last_updated = stored_data.get('timestamp')

        filtered_df = df_base.copy()

        # Пошук
        if search_term and str(search_term).strip():
            s = str(search_term).strip().lower()
            text_cols = ['product_name', 'supplier', 'category', 'url', 'color']
            mask = filtered_df[text_cols].fillna('').astype(str).apply(
                lambda row: row.str.lower().str.contains(s, na=False)
            ).any(axis=1)
            filtered_df = filtered_df[mask]

        if selected_suppliers:
            filtered_df = filtered_df[filtered_df['supplier'].isin(selected_suppliers)]
        if selected_categories:
            filtered_df = filtered_df[filtered_df['category'].isin(selected_categories)]
        if selected_availability:
            filtered_df = filtered_df[filtered_df['availability_code'].isin(selected_availability)]

        if filtered_df.empty:
            msg = html.Div([
                html.Div('🔍', style={'fontSize': '48px', 'marginBottom': '10px', 'opacity': 0.5}),
                html.H3('Нічого не знайдено', style={'color': 'var(--text-sub)', 'marginTop': 0}),
            ], style={'textAlign': 'center', 'padding': '40px', 'backgroundColor': 'var(--bg-card)', 'borderRadius': '12px'})
            return msg, f"🕒 Оновлено: {last_updated} | Знайдено: 0"

        table_header = html.Thead(html.Tr([
            html.Th('Постачальник', style={**TABLE_HEADER_STYLE}),
            html.Th('Назва Товару', style=TABLE_HEADER_STYLE),
            html.Th('Наявність', style={**TABLE_HEADER_STYLE, 'textAlign': 'center'}),
            html.Th('Ціна', style={**TABLE_HEADER_STYLE, 'textAlign': 'center'}),
            html.Th('Фото', style={**TABLE_HEADER_STYLE, 'textAlign': 'center'}),
            html.Th('Інфо', style={**TABLE_HEADER_STYLE, 'textAlign': 'center'}),
            html.Th('Дії', style={**TABLE_HEADER_STYLE, 'textAlign': 'center', 'width': '140px'}),
        ]))

        rows = []
        for _, row in filtered_df.iterrows():
            url = row.get('url')
            availability_code = row.get('availability_code', 'UNKNOWN')

            photo_cell = html.Td(
                html.Img(src=row['image_current'], style={
                    'height': '60px',
                    'width': '60px',
                    'objectFit': 'contain',
                    'borderRadius': '6px',
                    'backgroundColor': '#ffffff',
                    'padding': '2px',
                    'border': '1px solid var(--border)'
                }) if row.get('image_current') else html.Span('—', style={'opacity': 0.5}),
                style={**TABLE_CELL_STYLE, 'textAlign': 'center'}
            )

            status_badge = html.Span(
                row.get('availability_text', '—'),
                style=get_status_badge_style(availability_code)
            )

            refresh_single_button = html.Button(
                '🔄',
                id={'type': 'refresh-single-button', 'url': url},
                title="Оновити зараз",
                style={'background': 'none', 'border': 'none', 'cursor': 'pointer', 'fontSize': '16px', 'padding': '5px'}
            )
            edit_button = html.Button(
                '✏️',
                id={'type': 'edit-button', 'url': url},
                title="Редагувати",
                style={'background': 'none', 'border': 'none', 'cursor': 'pointer', 'fontSize': '16px', 'padding': '5px'}
            )
            delete_button = html.Button(
                '🗑️',
                id={'type': 'delete-button', 'url': url},
                title="Видалити",
                style={'background': 'none', 'border': 'none', 'cursor': 'pointer', 'fontSize': '16px', 'padding': '5px'}
            )

            info_block = html.Div([
                html.Div(f"{row.get('category', '—')}", style={'fontSize': '11px', 'opacity': 0.7}),
                html.Div(f"{row.get('color', '—')}", style={'fontSize': '11px', 'opacity': 0.7}),
            ])

            rows.append(html.Tr([
                html.Td(row.get('supplier', '—'), style={**TABLE_CELL_STYLE, 'fontWeight': '600'}),
                html.Td(
                    html.A(row.get('product_name', '—'), href=url, target='_blank',
                           style={'color': 'var(--info-text)', 'textDecoration': 'none', 'fontWeight': '500'}) if url else row.get('product_name', '—'),
                    style={**TABLE_CELL_STYLE}
                ),
                html.Td(status_badge, style={**TABLE_CELL_STYLE, 'textAlign': 'center'}),
                html.Td(html.Span(row.get('price_text', '—'), style={'fontWeight': '600'}),
                        style={**TABLE_CELL_STYLE, 'textAlign': 'center'}),
                photo_cell,
                html.Td(info_block, style={**TABLE_CELL_STYLE, 'textAlign': 'center'}),
                html.Td(
                    html.Div([refresh_single_button, edit_button, delete_button], style={'display': 'flex', 'gap': '5px', 'justifyContent': 'center'}),
                    style={**TABLE_CELL_STYLE, 'textAlign': 'center'}
                ),
            ]))

        table = html.Table([table_header, html.Tbody(rows)], style=TABLE_STYLE)
        status = f"🕒 Оновлено: {last_updated} | Відображено: {len(filtered_df)} з {len(df_base)}"
        return table, status

    except Exception as e:
        traceback.print_exc()
        return html.Div(f"Error: {e}"), dash.no_update


@app.callback(
    [Output('edit-modal-wrapper', 'style'),
     Output('edit-item-url', 'data'),
     Output('edit-product-name', 'value'),
     Output('edit-supplier', 'value'),
     Output('edit-category', 'value'),
     Output('edit-color', 'value'),
     Output('edit-url', 'value'),
     Output('edit-sel-availability', 'value'),
     Output('edit-sel-rrp', 'value'),
     Output('edit-sel-out-of-stock', 'value'),
     Output('edit-manual-image', 'value')],
    [Input({'type': 'edit-button', 'url': ALL}, 'n_clicks')],
    prevent_initial_call=True
)
def open_edit_modal(n_clicks_list):
    try:
        if not n_clicks_list or all(v is None or v == 0 for v in n_clicks_list):
            raise PreventUpdate

        ctx = dash.callback_context
        url = safe_get_triggered_url(ctx, "open_edit_modal")

        products_list = load_products()
        item = next((p for p in products_list if p.get('url') == url), None)
        if not item:
            raise PreventUpdate

        item = normalize_product_defaults(item)

        modal_style = {**MODAL_OVERLAY_STYLE, 'display': 'flex'}
        return (
            modal_style,
            url,
            item.get('product_name', ''),
            item.get('supplier', ''),
            item.get('category', ''),
            item.get('color', ''),
            item.get('url', ''),
            item.get('selectors', {}).get('availability'),
            item.get('selectors', {}).get('rrp_price'),
            item.get('selectors', {}).get('out_of_stock'),
            item.get('manual_image_url')
        )

    except TimeoutError:
        # ✅ NEW: lock timeout
        raise PreventUpdate

    except Exception:
        raise PreventUpdate


@app.callback(
    [Output('edit-modal-wrapper', 'style', allow_duplicate=True),
     Output('edit-item-url', 'data', allow_duplicate=True)],
    [Input('cancel-edit-button', 'n_clicks')],
    prevent_initial_call=True
)
def cancel_edit(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return {**MODAL_OVERLAY_STYLE, 'display': 'none'}, None


@app.callback(
    [Output('action-output-message', 'children', allow_duplicate=True),
     Output('data-refresh-trigger', 'data', allow_duplicate=True),
     Output('edit-modal-wrapper', 'style', allow_duplicate=True),
     Output('edit-item-url', 'data', allow_duplicate=True)],
    [Input('save-edit-button', 'n_clicks')],
    [State('edit-item-url', 'data'),
     State('edit-product-name', 'value'),
     State('edit-supplier', 'value'),
     State('edit-category', 'value'),
     State('edit-color', 'value'),
     State('edit-sel-availability', 'value'),
     State('edit-sel-rrp', 'value'),
     State('edit-sel-out-of-stock', 'value'),
     State('edit-manual-image', 'value'),
     State('data-refresh-trigger', 'data')],
    prevent_initial_call=True
)
def save_edit(n_clicks, item_url, product_name, supplier, category, color,
              sel_avail, sel_rrp, sel_out_of_stock, manual_image, refresh_trigger):
    if not n_clicks:
        raise PreventUpdate

    if not item_url:
        # ✅ FIX: callback expects 4 outputs, so we PreventUpdate
        raise PreventUpdate

    try:
        products_list = load_products()
        idx = next((i for i, p in enumerate(products_list) if p.get('url') == item_url), None)

        if idx is None:
            return (
                html.Span("Товар не знайдено.", style={'color': 'var(--danger)'}),
                dash.no_update,
                dash.no_update,
                dash.no_update
            )

        p = normalize_product_defaults(products_list[idx])

        p['product_name'] = product_name or p.get('product_name')
        p['supplier'] = supplier or 'Не вказано'
        p['category'] = (category.strip() if category else 'Не вказано')
        p['color'] = (color.strip() if color else '—')
        p['selectors'] = p.get('selectors', {}) or {}
        p['selectors']['availability'] = sel_avail or None
        p['selectors']['rrp_price'] = sel_rrp or None
        p['selectors']['out_of_stock'] = sel_out_of_stock or None
        p['selectors']['image'] = p.get('selectors', {}).get('image') # Keep existing if any
        p['manual_image_url'] = manual_image or None

        if p['manual_image_url']:
            p['image_current'] = p['manual_image_url']

        # Only upsert the edited product to save time and avoid timeouts
        save_products([p])

        msg = html.Span(
            "✅ Зміни збережено.",
            style={'color': 'var(--success-text)', 'padding': '10px', 'backgroundColor': 'var(--success-bg)', 'borderRadius': '8px', 'display': 'block'}
        )
        return msg, (refresh_trigger or 0) + 1, {**MODAL_OVERLAY_STYLE, 'display': 'none'}, None


    except Exception as e:
        return html.Span(f"{str(e)}", style={'color': 'var(--danger)'}), dash.no_update, dash.no_update, dash.no_update


@app.callback(
    [Output('action-output-message', 'children', allow_duplicate=True),
     Output('data-refresh-trigger', 'data', allow_duplicate=True)],
    [Input({'type': 'refresh-single-button', 'url': ALL}, 'n_clicks')],
    [State('data-refresh-trigger', 'data')],
    prevent_initial_call=True
)
def refresh_single_product(n_clicks_list, refresh_trigger):
    try:
        if not n_clicks_list or all(v is None or v == 0 for v in n_clicks_list):
            raise PreventUpdate

        ctx = dash.callback_context
        url = safe_get_triggered_url(ctx, "refresh_single_product")
        if not url:
            raise PreventUpdate

        # Load products to get the specific one
        products_list = load_products()
        product = next((p for p in products_list if p.get('url') == url), None)
        
        if not product:
            return (
                html.Span("Товар не знайдено в базі.", style={'color': 'var(--danger)'}),
                dash.no_update
            )

        # Scrape data
        async def scrape():
            import aiohttp
            from concurrent.futures import ThreadPoolExecutor
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                with ThreadPoolExecutor() as executor:
                    return await get_product_data_async(session, executor, product)

        res = asyncio.run(scrape())
        
        if res.get("error"):
             return (
                html.Span(f"Помилка оновлення: {res['error']}", style={'color': 'var(--danger)'}),
                dash.no_update
            )

        data = res.get("data")
        if not data:
             return (
                html.Span("Не вдалося отримати дані.", style={'color': 'var(--danger)'}),
                dash.no_update
            )

        # Update in DB
        def mutator(products):
            idx = next((i for i, p in enumerate(products) if p.get('url') == url), None)
            if idx is not None:
                p = normalize_product_defaults(products[idx])
                is_avail = data.get("is_available")
                price = data.get("price")
                
                now_iso = datetime.now().isoformat(timespec="seconds")
                now_legacy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                p.update({
                    "last_checked_iso": now_iso,
                    "last_checked": now_legacy,
                    "availability_code": "AVAILABLE" if is_avail else "OUT_OF_STOCK",
                    "availability_text": data.get("availability_text") or ("В наявності" if is_avail else "Немає в наявності"),
                    "price_current": price,
                    "price_text": format_price_text(price),
                    "image_current": p.get("manual_image_url") or data.get("image_url") or p.get("image_current"),
                    "is_available_last": is_avail,
                    "price_last": price,
                })
                # Let DB generate UUID for new products if id is missing or empty
                if not p.get('id') and 'id' in p:
                    del p['id']
                products[idx] = p
            return products

        update_products_locked(mutator)

        msg = html.Span(
            f"✅ Товар '{product.get('product_name')}' оновлено успішно.",
            style={'color': 'var(--success-text)', 'padding': '10px', 'backgroundColor': 'var(--success-bg)', 'borderRadius': '8px', 'display': 'block'}
        )
        return msg, (refresh_trigger or 0) + 1

    except Exception as e:
        logger.error(f"Error in refresh_single_product: {e}")
        return html.Span(f"{str(e)}", style={'color': 'var(--danger)'}), dash.no_update


@app.callback(
    [Output('action-output-message', 'children', allow_duplicate=True),
     Output('data-refresh-trigger', 'data', allow_duplicate=True)],
    [Input({'type': 'delete-button', 'url': ALL}, 'n_clicks')],
    [State('data-refresh-trigger', 'data')],
    prevent_initial_call=True
)
def delete_product(n_clicks_list, refresh_trigger):
    try:
        if not n_clicks_list or all(v is None or v == 0 for v in n_clicks_list):
            raise PreventUpdate

        ctx = dash.callback_context
        url = safe_get_triggered_url(ctx, "delete_product")

        delete_product_by_url(url)

        msg = html.Span(
            "✅ Товар видалено.",
            style={'color': 'var(--success-text)', 'padding': '10px', 'backgroundColor': 'var(--success-bg)', 'borderRadius': '8px', 'display': 'block'}
        )
        return msg, (refresh_trigger or 0) + 1

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Delete product error: {error_details}")
        return html.Div([
            html.Span(f"❌ Помилка видалення: {str(e)}", style={'color': 'var(--danger)', 'fontWeight': 'bold'}),
            html.Pre(error_details, style={'fontSize': '10px', 'marginTop': '10px', 'whiteSpace': 'pre-wrap'})
        ], style={'padding': '10px', 'backgroundColor': 'var(--danger-bg)', 'borderRadius': '8px'}), dash.no_update



# Аліас сервера для Vercel
application = server
app = server

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8050)
