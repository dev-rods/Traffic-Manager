
import json
import logging
import time
import traceback
import argparse
import os
from datetime import datetime
from importlib import import_module
from pathlib import Path

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def load_scripts():
    scripts_map = {}
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    if not scripts_dir.exists():
        logger.warning(f"Pasta de scripts não encontrada: {scripts_dir}")
        return scripts_map
    for script_file in scripts_dir.glob("*.py"):
        if script_file.name == "__init__.py":
            continue
        try:
            module_name = script_file.stem
            module_path = f"src.scripts.{module_name}"
            module = import_module(module_path)
            if hasattr(module, 'execute'):
                scripts_map[module_name] = module.execute
                logger.info(f"Script carregado: {module_name}")
            else:
                logger.warning(f"Script {module_name} não possui função 'execute'")
        except Exception as e:
            logger.error(f"Erro ao carregar script {script_file.name}: {str(e)}")
    
    return scripts_map

def load_config_from_file(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if 'command' not in config:
            raise ValueError("Arquivo JSON deve conter o campo 'command'")
        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao decodificar JSON: {str(e)}")

def handler(event, context):
    logger.info(f"Evento recebido: {json.dumps(event)}")
    start_time = time.time()
    try:
        scripts_map = load_scripts()
        if not scripts_map:
            raise ValueError("Nenhum script foi encontrado na pasta src/scripts")
        if 'p' in event:
            config = load_config_from_file(event['p'])
            command = config['command']
            params = {k: v for k, v in config.items() if k != 'command'}
        else:
            command = event.get('command') or event.get('script')
            params = event.get('params', {})
        if not command:
            raise ValueError('Nome do comando não especificado. Use o parâmetro "p" ou "command".')
        if command not in scripts_map:
            available_commands = ", ".join(scripts_map.keys())
            raise ValueError(f'Comando "{command}" não encontrado. Comandos disponíveis: {available_commands}')
        logger.info(f'Executando comando "{command}" com parâmetros: {json.dumps(params)}')
        script_function = scripts_map[command]
        result = script_function(params)
        duration = (time.time() - start_time) * 1000
        logger.info(f'Comando "{command}" executado com sucesso em {duration:.2f}ms')
        return {
            'success': True,
            'command': command,
            'result': result,
            'duration': duration,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        error_type = type(e).__name__
        error_message = str(e)
        stack_trace = traceback.format_exc()
        logger.error(f"Erro na execução do comando: {error_type} - {error_message}\n{stack_trace}")
        return {
            'success': False,
            'error': error_message,
            'errorType': error_type,
            'stack': stack_trace,
            'duration': duration,
            'timestamp': datetime.utcnow().isoformat()
        }
