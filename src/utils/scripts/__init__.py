"""
Módulo de scripts Python

Este arquivo importa todas as funções de script para disponibilizá-las no package.
"""
from src.utils.scripts.python.client_manager import (
    create_client,
    list_clients,
    regenerate_key,
    update_client_status,
    get_client
)

from src.utils.scripts.python.webhook_tester import (
    test_webhook
)

from src.utils.scripts.python.example_script import (
    calculate,
    generate_password
)

# Mapeamento de nomes de scripts para funções
SCRIPT_MAP = {
    # Scripts de gerenciamento de clientes
    'client:create': create_client,
    'client:list': list_clients,
    'client:regenerate-key': regenerate_key,
    'client:activate': lambda params: update_client_status({**params, 'active': True}),
    'client:deactivate': lambda params: update_client_status({**params, 'active': False}),
    'client:get': get_client,
    
    # Scripts para testes
    'webhook:test': test_webhook,
    
    # Scripts de exemplo
    'example:calculate': calculate,
    'example:password': generate_password
} 