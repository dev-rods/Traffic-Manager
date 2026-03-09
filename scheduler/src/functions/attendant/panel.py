import os
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PANEL_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Controle do Bot</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); padding: 32px; width: 100%; max-width: 400px; margin: 16px; }
h1 { font-size: 20px; color: #1a1a1a; margin-bottom: 24px; text-align: center; }
label { display: block; font-size: 13px; color: #666; margin-bottom: 4px; font-weight: 600; }
input, select { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 15px; margin-bottom: 16px; outline: none; }
input:focus, select:focus { border-color: #25d366; }
.btn-row { display: flex; gap: 8px; margin-top: 8px; }
button { flex: 1; padding: 12px; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: opacity 0.2s; }
button:active { opacity: 0.7; }
.btn-pause { background: #e74c3c; color: #fff; }
.btn-resume { background: #25d366; color: #fff; }
.btn-status { background: #f0f2f5; color: #333; border: 1px solid #ddd; }
#result { margin-top: 20px; padding: 12px; border-radius: 8px; font-size: 14px; display: none; }
.success { background: #d4edda; color: #155724; }
.error { background: #f8d7da; color: #721c24; }
.info { background: #d1ecf1; color: #0c5460; }
#status-badge { text-align: center; margin-bottom: 16px; display: none; }
.badge { display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 600; }
.badge-active { background: #d4edda; color: #155724; }
.badge-paused { background: #f8d7da; color: #721c24; }
</style>
</head>
<body>
<div class="card">
<h1>Controle do Bot</h1>
<div id="status-badge"><span class="badge" id="badge-text"></span></div>
<label>Clinica</label>
<select id="clinic_id">
<option value="">Carregando...</option>
</select>
<label>Telefone do cliente</label>
<input type="tel" id="phone" placeholder="55 11 99999-9999">
<div class="btn-row">
<button class="btn-pause" onclick="callApi('activate')">Pausar Bot</button>
<button class="btn-resume" onclick="callApi('deactivate')">Retomar Bot</button>
</div>
<div class="btn-row" style="margin-top:8px">
<button class="btn-status" onclick="checkStatus()">Verificar Status</button>
</div>
<div id="result"></div>
</div>
<script>
const pathParts = window.location.pathname.split('/');
const STAGE = pathParts[1] || 'dev';
const BASE = window.location.origin + '/' + STAGE;
const API_KEY = localStorage.getItem('scheduler_api_key') || prompt('Digite a API Key:');
if (API_KEY) localStorage.setItem('scheduler_api_key', API_KEY);

async function loadClinics() {
  try {
    const r = await fetch(BASE + '/clinics', { headers: { 'x-api-key': API_KEY } });
    const data = await r.json();
    const sel = document.getElementById('clinic_id');
    sel.innerHTML = '';
    const clinics = data.clinics || data || [];
    if (Array.isArray(clinics)) {
      clinics.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.clinic_id;
        opt.textContent = c.name || c.clinic_id;
        sel.appendChild(opt);
      });
    }
  } catch(e) { console.error('Erro ao carregar clinicas:', e); }
}
loadClinics();

function showResult(msg, type) {
  const el = document.getElementById('result');
  el.textContent = msg;
  el.className = type;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 5000);
}

async function callApi(action) {
  const clinic_id = document.getElementById('clinic_id').value;
  const phone = document.getElementById('phone').value.replace(/\\D/g, '');
  if (!clinic_id || !phone) { showResult('Preencha clinica e telefone', 'error'); return; }
  try {
    const r = await fetch(BASE + '/attendant/' + action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
      body: JSON.stringify({ clinic_id, phone })
    });
    const data = await r.json();
    if (r.ok) {
      showResult(data.message, 'success');
      checkStatus();
    } else {
      showResult(data.message || 'Erro', 'error');
    }
  } catch(e) { showResult('Erro de conexao: ' + e.message, 'error'); }
}

async function checkStatus() {
  const clinic_id = document.getElementById('clinic_id').value;
  const phone = document.getElementById('phone').value.replace(/\\D/g, '');
  if (!clinic_id || !phone) { showResult('Preencha clinica e telefone', 'error'); return; }
  try {
    const r = await fetch(BASE + '/attendant/status?clinic_id=' + clinic_id + '&phone=' + phone, {
      headers: { 'x-api-key': API_KEY }
    });
    const data = await r.json();
    const badge = document.getElementById('status-badge');
    const text = document.getElementById('badge-text');
    badge.style.display = 'block';
    if (data.bot_paused) {
      const mins = Math.round((data.ttl_remaining_seconds || 0) / 60);
      text.className = 'badge badge-paused';
      text.textContent = 'Bot PAUSADO (' + mins + ' min restantes)';
    } else {
      text.className = 'badge badge-active';
      text.textContent = 'Bot ATIVO';
    }
  } catch(e) { showResult('Erro: ' + e.message, 'error'); }
}
</script>
</body>
</html>"""


def handler(event, context):
    """Serves the attendant control panel HTML."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
        },
        "body": PANEL_HTML,
    }
