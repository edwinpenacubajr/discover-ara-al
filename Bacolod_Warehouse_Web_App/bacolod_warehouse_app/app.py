import io
from datetime import date, timedelta
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title='Bacolod Warehouse Monitoring', page_icon='📦', layout='wide')

FIELDS = ['Trx Date','DR No.','From W/H','Ship To','Status','Received Date / Memo','Memo']

st.markdown('''<style>
.block-container {padding-top:1.7rem;max-width:1450px}
[data-testid="stMetric"] {border:1px solid rgba(125,125,125,.22);border-radius:15px;padding:15px}
h1,h2,h3 {letter-spacing:-.03em}
</style>''', unsafe_allow_html=True)

def parse_dates(series):
    return pd.to_datetime(series, errors='coerce').dt.normalize()

def import_data(upload):
    raw = pd.read_csv(upload, header=None, dtype=str) if upload.name.lower().endswith('.csv') else pd.read_excel(upload, header=None, dtype=str)
    idx = None
    for i in range(min(len(raw), 30)):
        row = ' '.join(raw.iloc[i].fillna('').astype(str).str.lower().tolist())
        if ('trx date' in row or 'transaction date' in row) and 'dr no' in row:
            idx = i
            break
    if idx is None:
        raise ValueError('Could not find the Trx Date / DR No. header row. Export the delivery sheet (not a report tab).')
    values = raw.iloc[idx+1:, :7].copy()
    values.columns = FIELDS
    values = values.dropna(how='all').reset_index(drop=True)
    values = values.fillna('')
    values = values[values['DR No.'].astype(str).str.strip().ne('')].reset_index(drop=True)
    values['Shipping Method'] = ''
    values['Actual Received Date'] = ''
    return values

def calculate(data):
    df = data.copy()
    for col in FIELDS + ['Shipping Method','Actual Received Date']:
        if col not in df:
            df[col] = ''
    df['Trx Date'] = parse_dates(df['Trx Date'])
    df['Actual Received Date'] = parse_dates(df['Actual Received Date'])
    origin = df['From W/H'].fillna('').astype(str).str.upper()
    method = df['Shipping Method'].fillna('').astype(str).str.upper().str.strip()
    memo = (df['Memo'].fillna('').astype(str) + ' ' + df['Received Date / Memo'].fillna('').astype(str)).str.upper()
    method = method.where(method.isin(['AIR','SEA']), '')
    inferred = pd.Series('', index=df.index)
    inferred.loc[memo.str.contains(r'\bAIR\b|VIA AIR', regex=True)] = 'AIR'
    inferred.loc[memo.str.contains(r'\bSEA\b|VIA SEA', regex=True)] = 'SEA'
    method = method.where(method.ne(''), inferred)
    manila = origin.str.contains('MANILA|MNL', regex=True)
    cebu = origin.str.contains('CEBU|MANDAUE|HERNAN', regex=True)
    min_days = pd.Series(pd.NA, index=df.index, dtype='Int64')
    max_days = pd.Series(pd.NA, index=df.index, dtype='Int64')
    min_days.loc[cebu] = 2
    max_days.loc[cebu] = 4
    min_days.loc[manila & method.eq('AIR')] = 2
    max_days.loc[manila & method.eq('AIR')] = 4
    min_days.loc[manila & method.eq('SEA')] = 15
    max_days.loc[manila & method.eq('SEA')] = 20
    df['Method Used'] = method.where(manila, 'LAND/SEA')
    df['Lead Time'] = min_days.astype('string').fillna('?') + '–' + max_days.astype('string').fillna('?') + ' days'
    df['Expected Arrival'] = df['Trx Date'] + pd.to_timedelta(max_days.astype('float'), unit='D')
    received = df['Status'].fillna('').astype(str).str.upper().str.contains('RECEIVED')
    today = pd.Timestamp(date.today())
    df['Monitoring Status'] = 'PENDING'
    df.loc[df['Trx Date'].isna() | max_days.isna(), 'Monitoring Status'] = 'CHECK DATA'
    df.loc[~received & df['Expected Arrival'].notna() & (df['Expected Arrival'] < today), 'Monitoring Status'] = 'OVERDUE'
    df.loc[received, 'Monitoring Status'] = 'RECEIVED'
    df['Days Overdue'] = (today - df['Expected Arrival']).dt.days.clip(lower=0).fillna(0).astype(int)
    df.loc[df['Monitoring Status'] != 'OVERDUE', 'Days Overdue'] = 0
    return df

st.title('📦 Bacolod Warehouse Monitoring')
st.caption('Delivery intelligence • Manila / Cebu → Bacolod • Philippine calendar days')

with st.sidebar:
    st.header('Workspace')
    uploaded = st.file_uploader('Import original delivery sheet', type=['xlsx','csv'])
    st.info('Your original Google Sheet is never modified. Upload a fresh export when its records change.')
    st.caption('Manila Air 2–4 days · Manila Sea 15–20 days · Cebu 2–4 days')
    st.caption('Changes are temporary until you download the edited CSV.')

if uploaded is not None:
    signature = (uploaded.name, uploaded.size)
    if st.session_state.get('signature') != signature:
        try:
            st.session_state['data'] = import_data(uploaded)
            st.session_state['signature'] = signature
        except Exception as exc:
            st.error(str(exc))
            st.stop()

if 'data' not in st.session_state:
    st.subheader('Start by importing your delivery records')
    st.write('In Google Sheets: **File → Download → Microsoft Excel (.xlsx)**, then upload that file in the sidebar. If the workbook has multiple tabs, export the delivery tab as CSV instead.')
    st.stop()

source = st.session_state['data']
df = calculate(source)

with st.expander('✏️ Edit shipping methods, receipt dates and delivery records', expanded=False):
    st.caption('For Manila records without AIR or SEA in the memo, enter the shipping method below. Save changes using the download button.')
    edited = st.data_editor(source, use_container_width=True, num_rows='dynamic', hide_index=True,
                            column_config={'Shipping Method': st.column_config.SelectboxColumn('Shipping Method', options=['','AIR','SEA']),
                                           'Trx Date': st.column_config.TextColumn('Trx Date (YYYY-MM-DD)'),
                                           'Actual Received Date': st.column_config.TextColumn('Actual Received Date (YYYY-MM-DD)')},
                            key='delivery_editor')
    if st.button('Apply edits', type='primary'):
        st.session_state['data'] = edited.fillna('').astype(str)
        st.rerun()

statuses = ['ALL','RECEIVED','PENDING','OVERDUE','CHECK DATA']
left,right = st.columns([1,2])
with left:
    status_filter = st.selectbox('Status filter', statuses)
with right:
    search = st.text_input('Search DR number, origin, destination or memo', placeholder='e.g. 62791 or MANILA')
view = df.copy()
if status_filter != 'ALL':
    view = view[view['Monitoring Status'].eq(status_filter)]
if search:
    mask = view[['DR No.','From W/H','Ship To','Memo']].fillna('').astype(str).apply(lambda col: col.str.contains(search, case=False, regex=False)).any(axis=1)
    view = view[mask]

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric('Total',len(df))
for widget,status in zip([m2,m3,m4,m5],statuses[1:]):
    widget.metric(status.title(),int(df['Monitoring Status'].eq(status).sum()))

tab1,tab2,tab3 = st.tabs(['📊 Dashboard','🚚 Deliveries & Alerts','📑 Reports'])
with tab1:
    a,b = st.columns(2)
    with a:
        counts = df['Monitoring Status'].value_counts().rename_axis('Status').reset_index(name='Count')
        st.plotly_chart(px.pie(counts,names='Status',values='Count',hole=.6,title='Delivery status'),use_container_width=True)
    with b:
        monthly = df.dropna(subset=['Trx Date']).copy()
        monthly['Month'] = monthly['Trx Date'].dt.strftime('%Y-%m')
        counts = monthly.groupby(['Month','Monitoring Status']).size().reset_index(name='Deliveries')
        if len(counts):
            st.plotly_chart(px.bar(counts,x='Month',y='Deliveries',color='Monitoring Status',title='Monthly delivery volume'),use_container_width=True)
        else:
            st.info('No valid transaction dates to chart.')
    if df['Monitoring Status'].eq('CHECK DATA').any():
        st.warning('Some shipments need a valid transaction date, recognized origin, or Manila shipping method.')
with tab2:
    overdue = df[df['Monitoring Status'].eq('OVERDUE')]
    if len(overdue):
        st.error(f'{len(overdue)} delivery record(s) overdue as of {date.today().isoformat()}.')
        st.dataframe(overdue[['DR No.','Trx Date','From W/H','Ship To','Expected Arrival','Days Overdue','Memo']],hide_index=True,use_container_width=True)
    else:
        st.success('No overdue records based on currently imported data.')
    st.subheader('All monitored deliveries')
    st.dataframe(view,hide_index=True,use_container_width=True)
with tab3:
    period = st.radio('Report period',['Daily','Weekly','Monthly'],horizontal=True)
    reports = df.copy()
    reports['Period'] = 'Missing date'
    valid = reports['Trx Date'].notna()
    if period == 'Daily':
        reports.loc[valid,'Period'] = reports.loc[valid,'Trx Date'].dt.strftime('%Y-%m-%d')
    elif period == 'Weekly':
        reports.loc[valid,'Period'] = reports.loc[valid,'Trx Date'].dt.to_period('W-SUN').astype(str)
    else:
        reports.loc[valid,'Period'] = reports.loc[valid,'Trx Date'].dt.strftime('%Y-%m')
    summary = pd.crosstab(reports['Period'],reports['Monitoring Status'])
    for name in statuses[1:]:
        if name not in summary: summary[name] = 0
    summary['Total'] = summary[statuses[1:]].sum(axis=1)
    summary = summary[['Total']+statuses[1:]].reset_index().sort_values('Period',ascending=False)
    st.dataframe(summary,hide_index=True,use_container_width=True)
    st.download_button('Download report CSV',summary.to_csv(index=False).encode('utf-8-sig'),file_name=f'bacolod_{period.lower()}_report.csv',mime='text/csv')

export = source.copy()
for c in ['Trx Date','Actual Received Date']:
    export[c] = pd.to_datetime(export[c],errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
st.download_button('⬇️ Download edited delivery data CSV',export.to_csv(index=False).encode('utf-8-sig'),file_name='bacolod_delivery_data.csv',mime='text/csv')
st.caption('Note: Dashboard recalculates on interaction and refresh. No live Google Sheets connection or background alerts are configured.')
