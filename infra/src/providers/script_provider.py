"""
Módulo de providers

Este módulo provê funções auxiliares para invocar os scripts diretamente
a partir de outros módulos Python, além de invocar a função lambda.
"""
import json
import time
import boto3
import os
import logging
from datetime import datetime
from src.utils.scripts.python import SCRIPT_MAP

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class ScriptProvider:
    """
    Classe para invocar scripts de forma programática
    """
    
    def __init__(self, options=None):
        """
        Inicializa o provider de scripts
        
        Args:
            options (dict, optional): Opções de configuração
                - lambda_config (dict): Configurações do cliente Lambda
                - function_name (str): Nome da função Lambda
                - prefer_local (bool): Preferência por execução local
        """
        options = options or {}
        self.lambda_client = boto3.client('lambda', **options.get('lambda_config', {}))
        self.function_name = options.get('function_name') or os.environ.get('BASE_FUNCTION_NAME', '') + 'ScriptManager'
        self.prefer_local = options.get('prefer_local', True)
    
    def invoke(self, script_name, params=None, options=None):
        """
        Invoca um script pelo nome
        
        Args:
            script_name (str): Nome do script
            params (dict, optional): Parâmetros do script
            options (dict, optional): Opções adicionais
                - force_lambda (bool): Força o uso da Lambda mesmo localmente
                
        Returns:
            dict: Resultado da execução do script
        """
        options = options or {}
        params = params or {}
        
        # Se prefer_local é True e não está forçando Lambda, e estamos em ambiente de desenvolvimento
        if self.prefer_local and not options.get('force_lambda') and os.environ.get('STAGE') in ['dev', 'development']:
            return self.invoke_local(script_name, params)
        
        # Caso contrário, invoca a função Lambda
        return self.invoke_lambda(script_name, params)
    
    def invoke_local(self, script_name, params=None):
        """
        Invoca um script localmente
        
        Args:
            script_name (str): Nome do script
            params (dict, optional): Parâmetros do script
            
        Returns:
            dict: Resultado do script
        """
        logger.info(f'Invocando script "{script_name}" localmente')
        params = params or {}
        
        if script_name not in SCRIPT_MAP:
            raise ValueError(f'Script "{script_name}" não encontrado')
        
        try:
            start_time = time.time()
            result = SCRIPT_MAP[script_name](params)
            duration = (time.time() - start_time) * 1000  # em milissegundos
            
            return {
                'success': True,
                'scriptName': script_name,
                'result': result,
                'duration': duration,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise ValueError(f'Erro ao executar script "{script_name}": {str(e)}')
    
    def invoke_lambda(self, script_name, params=None):
        """
        Invoca um script através da função Lambda
        
        Args:
            script_name (str): Nome do script
            params (dict, optional): Parâmetros do script
            
        Returns:
            dict: Resultado do script
        """
        logger.info(f'Invocando script "{script_name}" via Lambda')
        params = params or {}
        
        payload = {
            'script': script_name,
            'params': params
        }
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.function_name,
                Payload=json.dumps(payload).encode()
            )
            
            # Parse do resultado
            result = json.loads(response['Payload'].read().decode())
            
            if not result.get('success'):
                raise ValueError(result.get('error') or 'Erro desconhecido na execução do script')
            
            return result
        except Exception as e:
            raise ValueError(f'Erro ao invocar Lambda para script "{script_name}": {str(e)}') 