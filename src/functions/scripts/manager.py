"""
Gerenciador de execução de scripts

Este módulo contém a função Lambda que recebe um nome de script e parâmetros,
executa o script apropriado e retorna o resultado.
"""
import json
import logging
import time
import traceback
from datetime import datetime

from src.utils.scripts.python import SCRIPT_MAP

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Função principal do gerenciador de scripts
    
    Args:
        event (dict): Evento da Lambda
            - script (str): Nome do script a ser executado
            - params (dict): Parâmetros para o script
        context (LambdaContext): Contexto da Lambda
        
    Returns:
        dict: Resultado da execução do script
    """
    logger.info(f"Evento recebido: {json.dumps(event)}")
    
    start_time = time.time()
    
    try:
        # Verificar se o script foi especificado
        if 'script' not in event:
            raise ValueError('Nome do script não especificado. Use o parâmetro "script".')
        
        script_name = event['script']
        params = event.get('params', {})
        
        # Verificar se o script existe
        if script_name not in SCRIPT_MAP:
            available_scripts = ", ".join(SCRIPT_MAP.keys())
            raise ValueError(f'Script "{script_name}" não encontrado. Scripts disponíveis: {available_scripts}')
        
        logger.info(f'Executando script "{script_name}" com parâmetros: {json.dumps(params)}')
        
        # Executar o script
        script_function = SCRIPT_MAP[script_name]
        result = script_function(params)
        
        # Calcular duração
        duration = (time.time() - start_time) * 1000  # em milissegundos
        
        logger.info(f'Script "{script_name}" executado com sucesso em {duration:.2f}ms')
        
        return {
            'success': True,
            'scriptName': script_name,
            'result': result,
            'duration': duration,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        # Calcular duração mesmo para erros
        duration = (time.time() - start_time) * 1000  # em milissegundos
        
        error_type = type(e).__name__
        error_message = str(e)
        stack_trace = traceback.format_exc()
        
        logger.error(f"Erro na execução do script: {error_type} - {error_message}\n{stack_trace}")
        
        return {
            'success': False,
            'error': error_message,
            'errorType': error_type,
            'stack': stack_trace,
            'duration': duration,
            'timestamp': datetime.utcnow().isoformat()
        } 