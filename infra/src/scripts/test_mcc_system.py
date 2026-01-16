#!/usr/bin/env python
"""
Testes para validar o processo de associação MCC do Google Ads

Este script testa todas as funcionalidades relacionadas ao MCC:
- Envio de convites
- Verificação de status
- Monitoramento
- Integração com criação de clientes
"""

import os
import sys
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Adicionar src ao path para imports
sys.path.append(str(Path(__file__).parent.parent))

from services.google_ads_mcc_service import GoogleAdsMCCService
from scripts.create_client import execute as create_client
from scripts.monitor_mcc_status import execute as monitor_mcc_status

class TestGoogleAdsMCCService(unittest.TestCase):
    """Testes para o serviço MCC"""
    
    def setUp(self):
        """Configuração inicial dos testes"""
        # Mock das variáveis de ambiente
        self.env_patcher = patch.dict(os.environ, {
            'GOOGLE_ADS_DEVELOPER_TOKEN': 'test_developer_token',
            'OAUTH2_CLIENT_ID': 'test_client_id',
            'OAUTH2_CLIENT_SECRET': 'test_client_secret',
            'GOOGLE_ADS_REFRESH_TOKEN': 'test_refresh_token',
            'MCC_CUSTOMER_ID': '1234567890',
            'CLIENTS_TABLE': 'test-clients-table',
            'EXECUTION_HISTORY_TABLE': 'test-execution-history-table'
        })
        self.env_patcher.start()
        
        # Mock do DynamoDB
        self.dynamodb_patcher = patch('boto3.resource')
        self.mock_dynamodb = self.dynamodb_patcher.start()
        
        # Mock das tabelas
        self.mock_clients_table = Mock()
        self.mock_execution_table = Mock()
        
        mock_dynamodb_instance = Mock()
        mock_dynamodb_instance.Table.side_effect = lambda table_name: {
            'test-clients-table': self.mock_clients_table,
            'test-execution-history-table': self.mock_execution_table
        }.get(table_name, Mock())
        
        self.mock_dynamodb.return_value = mock_dynamodb_instance
        
        # Mock do Google Ads Client
        self.google_ads_patcher = patch('google.ads.googleads.client.GoogleAdsClient')
        self.mock_google_ads_client = self.google_ads_patcher.start()
        
        # Mock do serviço MCC
        self.mcc_service = GoogleAdsMCCService()
    
    def tearDown(self):
        """Limpeza após os testes"""
        self.env_patcher.stop()
        self.dynamodb_patcher.stop()
        self.google_ads_patcher.stop()
    
    def test_get_mcc_client_success(self):
        """Testa criação bem-sucedida do cliente MCC"""
        # Mock do cliente Google Ads
        mock_client_instance = Mock()
        self.mock_google_ads_client.load_from_dict.return_value = mock_client_instance
        
        client = self.mcc_service.get_mcc_client()
        
        self.assertIsNotNone(client)
        self.assertEqual(client, mock_client_instance)
        self.mock_google_ads_client.load_from_dict.assert_called_once()
    
    def test_get_mcc_client_missing_config(self):
        """Testa falha na criação do cliente MCC por configuração ausente"""
        # Remover variável de ambiente
        with patch.dict(os.environ, {'GOOGLE_ADS_DEVELOPER_TOKEN': ''}):
            mcc_service = GoogleAdsMCCService()
            client = mcc_service.get_mcc_client()
            
            self.assertIsNone(client)
    
    @patch('src.services.google_ads_mcc_service.GoogleAdsException')
    def test_send_link_invitation_success(self, mock_google_ads_exception):
        """Testa envio bem-sucedido de convite MCC"""
        # Mock do cliente MCC
        mock_client = Mock()
        self.mcc_service._mcc_client_cache = mock_client
        
        # Mock do serviço CustomerClientLinkService
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service
        
        # Mock da resposta
        mock_response = Mock()
        mock_response.results = [Mock()]
        mock_response.results[0].resource_name = "customers/1234567890/customerClientLinks/9876543210"
        mock_service.mutate_customer_client_link.return_value = mock_response
        
        # Mock do DynamoDB put_item
        self.mock_execution_table.put_item = Mock()
        
        result = self.mcc_service.send_link_invitation("9876543210", "Cliente Teste")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['link_id'], "9876543210")
        self.assertEqual(result['status'], 'PENDING')
        self.mock_execution_table.put_item.assert_called_once()
    
    @patch('src.services.google_ads_mcc_service.GoogleAdsException')
    def test_send_link_invitation_error(self, mock_google_ads_exception):
        """Testa erro no envio de convite MCC"""
        # Mock do cliente MCC
        mock_client = Mock()
        self.mcc_service._mcc_client_cache = mock_client
        
        # Mock do serviço CustomerClientLinkService
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service
        
        # Mock de erro
        mock_error = Mock()
        mock_error.code.return_value.name = "PERMISSION_DENIED"
        mock_error.message = "Sem permissão para enviar convite"
        
        mock_exception = Mock()
        mock_exception.error = mock_error
        mock_service.mutate_customer_client_link.side_effect = mock_exception
        
        result = self.mcc_service.send_link_invitation("9876543210", "Cliente Teste")
        
        self.assertFalse(result['success'])
        self.assertIn("PERMISSION_DENIED", result['error'])
    
    def test_get_link_status_found(self):
        """Testa verificação de status quando link é encontrado"""
        # Mock do cliente MCC
        mock_client = Mock()
        self.mcc_service._mcc_client_cache = mock_client
        
        # Mock do serviço CustomerClientLinkService
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service
        
        # Mock da resposta
        mock_response = Mock()
        mock_response.status.name = "APPROVED"
        mock_response.resource_name = "customers/1234567890/customerClientLinks/9876543210"
        mock_response.creation_date_time = "2024-01-01T00:00:00Z"
        mock_service.get_customer_client_link.return_value = mock_response
        
        result = self.mcc_service.get_link_status("9876543210")
        
        self.assertTrue(result['found'])
        self.assertEqual(result['status'], 'APPROVED')
        self.assertEqual(result['link_id'], '9876543210')
    
    def test_get_link_status_not_found(self):
        """Testa verificação de status quando link não é encontrado"""
        # Mock do cliente MCC
        mock_client = Mock()
        self.mcc_service._mcc_client_cache = mock_client
        
        # Mock do serviço CustomerClientLinkService
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service
        
        # Mock de erro NOT_FOUND
        from google.ads.googleads.errors import GoogleAdsException
        mock_error = Mock()
        mock_error.code.return_value.name = "NOT_FOUND"
        
        mock_exception = GoogleAdsException()
        mock_exception.error = mock_error
        mock_service.get_customer_client_link.side_effect = mock_exception
        
        result = self.mcc_service.get_link_status("9876543210")
        
        self.assertFalse(result['found'])
        self.assertEqual(result['status'], 'NOT_LINKED')
    
    def test_list_all_links(self):
        """Testa listagem de todas as associações"""
        # Mock do cliente MCC
        mock_client = Mock()
        self.mcc_service._mcc_client_cache = mock_client
        
        # Mock do GoogleAdsService
        mock_ga_service = Mock()
        mock_client.get_service.side_effect = lambda service_name: mock_ga_service if service_name == "GoogleAdsService" else Mock()
        
        # Mock do stream de resultados
        mock_batch = Mock()
        mock_row = Mock()
        mock_row.customer_client_link.resource_name = "customers/1234567890/customerClientLinks/9876543210"
        mock_row.customer_client_link.status.name = "APPROVED"
        mock_row.customer_client_link.client_customer = "customers/9876543210"
        mock_row.customer_client_link.creation_date_time = "2024-01-01T00:00:00Z"
        
        mock_batch.results = [mock_row]
        mock_ga_service.search_stream.return_value = [mock_batch]
        
        result = self.mcc_service.list_all_links()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'APPROVED')
        self.assertEqual(result[0]['client_customer_id'], '9876543210')

class TestCreateClientIntegration(unittest.TestCase):
    """Testes para integração MCC na criação de clientes"""
    
    def setUp(self):
        """Configuração inicial dos testes"""
        # Mock das variáveis de ambiente
        self.env_patcher = patch.dict(os.environ, {
            'CLIENTS_TABLE': 'test-clients-table',
            'GOOGLE_ADS_DEVELOPER_TOKEN': 'test_token',
            'OAUTH2_CLIENT_ID': 'test_client_id',
            'OAUTH2_CLIENT_SECRET': 'test_secret',
            'GOOGLE_ADS_REFRESH_TOKEN': 'test_refresh',
            'MCC_CUSTOMER_ID': '1234567890'
        })
        self.env_patcher.start()
        
        # Mock do DynamoDB
        self.dynamodb_patcher = patch('boto3.resource')
        self.mock_dynamodb = self.dynamodb_patcher.start()
        
        # Mock das tabelas
        self.mock_clients_table = Mock()
        mock_dynamodb_instance = Mock()
        mock_dynamodb_instance.Table.return_value = self.mock_clients_table
        self.mock_dynamodb.return_value = mock_dynamodb_instance
    
    def tearDown(self):
        """Limpeza após os testes"""
        self.env_patcher.stop()
        self.dynamodb_patcher.stop()
    
    @patch('src.scripts.create_client.GoogleAdsMCCService')
    def test_create_client_with_mcc_success(self, mock_mcc_service_class):
        """Testa criação de cliente com envio bem-sucedido de convite MCC"""
        # Mock do serviço MCC
        mock_mcc_service = Mock()
        mock_mcc_service_class.return_value = mock_mcc_service
        mock_mcc_service.send_link_invitation.return_value = {
            'success': True,
            'link_id': 'test_link_id',
            'status': 'PENDING'
        }
        
        # Mock do DynamoDB
        self.mock_clients_table.put_item = Mock()
        self.mock_clients_table.update_item = Mock()
        
        params = {
            "name": "Cliente Teste",
            "email": "teste@exemplo.com",
            "googleAdsCustomerId": "9876543210",
            "sendMccInvitation": True
        }
        
        result = create_client(params)
        
        # Verificações
        self.assertEqual(result["name"], "Cliente Teste")
        self.assertEqual(result["googleAdsCustomerId"], "9876543210")
        self.assertEqual(result["mccStatus"], "NOT_LINKED")  # Status inicial
        
        # Verificar se convite MCC foi enviado
        mock_mcc_service.send_link_invitation.assert_called_once_with("9876543210", "Cliente Teste")
        
        # Verificar se DynamoDB foi chamado
        self.mock_clients_table.put_item.assert_called_once()
        self.mock_clients_table.update_item.assert_called_once()
    
    @patch('src.scripts.create_client.GoogleAdsMCCService')
    def test_create_client_with_mcc_error(self, mock_mcc_service_class):
        """Testa criação de cliente com erro no envio de convite MCC"""
        # Mock do serviço MCC
        mock_mcc_service = Mock()
        mock_mcc_service_class.return_value = mock_mcc_service
        mock_mcc_service.send_link_invitation.return_value = {
            'success': False,
            'error': 'Erro de permissão'
        }
        
        # Mock do DynamoDB
        self.mock_clients_table.put_item = Mock()
        self.mock_clients_table.update_item = Mock()
        
        params = {
            "name": "Cliente Teste",
            "email": "teste@exemplo.com",
            "googleAdsCustomerId": "9876543210",
            "sendMccInvitation": True
        }
        
        result = create_client(params)
        
        # Verificações
        self.assertEqual(result["name"], "Cliente Teste")
        self.assertFalse(result["mccInvitation"]["success"])
        self.assertEqual(result["mccInvitation"]["error"], "Erro de permissão")
        
        # Verificar se DynamoDB foi chamado para atualizar status de erro
        self.mock_clients_table.update_item.assert_called_once()
    
    def test_create_client_without_mcc(self):
        """Testa criação de cliente sem envio de convite MCC"""
        # Mock do DynamoDB
        self.mock_clients_table.put_item = Mock()
        
        params = {
            "name": "Cliente Teste",
            "email": "teste@exemplo.com",
            "googleAdsCustomerId": "9876543210",
            "sendMccInvitation": False
        }
        
        result = create_client(params)
        
        # Verificações
        self.assertEqual(result["name"], "Cliente Teste")
        self.assertEqual(result["mccStatus"], "NOT_LINKED")
        self.assertIsNone(result["mccInvitation"])
        
        # Verificar se apenas put_item foi chamado (sem update_item)
        self.mock_clients_table.put_item.assert_called_once()
        self.mock_clients_table.update_item.assert_not_called()

class TestMonitorMCCStatus(unittest.TestCase):
    """Testes para monitoramento de status MCC"""
    
    def setUp(self):
        """Configuração inicial dos testes"""
        # Mock das variáveis de ambiente
        self.env_patcher = patch.dict(os.environ, {
            'CLIENTS_TABLE': 'test-clients-table',
            'GOOGLE_ADS_DEVELOPER_TOKEN': 'test_token',
            'OAUTH2_CLIENT_ID': 'test_client_id',
            'OAUTH2_CLIENT_SECRET': 'test_secret',
            'GOOGLE_ADS_REFRESH_TOKEN': 'test_refresh',
            'MCC_CUSTOMER_ID': '1234567890'
        })
        self.env_patcher.start()
        
        # Mock do DynamoDB
        self.dynamodb_patcher = patch('boto3.resource')
        self.mock_dynamodb = self.dynamodb_patcher.start()
        
        # Mock das tabelas
        self.mock_clients_table = Mock()
        mock_dynamodb_instance = Mock()
        mock_dynamodb_instance.Table.return_value = self.mock_clients_table
        self.mock_dynamodb.return_value = mock_dynamodb_instance
    
    def tearDown(self):
        """Limpeza após os testes"""
        self.env_patcher.stop()
        self.dynamodb_patcher.stop()
    
    @patch('src.scripts.monitor_mcc_status.GoogleAdsMCCService')
    def test_monitor_all_clients(self, mock_mcc_service_class):
        """Testa monitoramento de todos os clientes"""
        # Mock do serviço MCC
        mock_mcc_service = Mock()
        mock_mcc_service_class.return_value = mock_mcc_service
        mock_mcc_service.get_link_status.return_value = {
            'found': True,
            'status': 'APPROVED',
            'link_id': 'test_link_id',
            'created_date': '2024-01-01T00:00:00Z'
        }
        
        # Mock do DynamoDB scan
        self.mock_clients_table.scan.return_value = {
            'Items': [
                {
                    'clientId': 'cliente1',
                    'googleAdsCustomerId': '1111111111',
                    'mccStatus': 'PENDING'
                },
                {
                    'clientId': 'cliente2',
                    'googleAdsCustomerId': '2222222222',
                    'mccStatus': 'PENDING'
                }
            ]
        }
        
        self.mock_clients_table.update_item = Mock()
        
        result = monitor_mcc_status({"check_all": True, "update_status": True})
        
        # Verificações
        self.assertEqual(result['checked_clients'], 2)
        self.assertEqual(result['updated_clients'], 2)
        self.assertEqual(result['approved_links'], 2)
        
        # Verificar se get_link_status foi chamado para cada cliente
        self.assertEqual(mock_mcc_service.get_link_status.call_count, 2)
        
        # Verificar se update_item foi chamado para cada cliente
        self.assertEqual(self.mock_clients_table.update_item.call_count, 2)
    
    @patch('src.scripts.monitor_mcc_status.GoogleAdsMCCService')
    def test_monitor_specific_client(self, mock_mcc_service_class):
        """Testa monitoramento de cliente específico"""
        # Mock do serviço MCC
        mock_mcc_service = Mock()
        mock_mcc_service_class.return_value = mock_mcc_service
        mock_mcc_service.get_link_status.return_value = {
            'found': True,
            'status': 'REJECTED',
            'link_id': 'test_link_id'
        }
        
        # Mock do DynamoDB get_item
        self.mock_clients_table.get_item.return_value = {
            'Item': {
                'clientId': 'cliente1',
                'googleAdsCustomerId': '1111111111',
                'mccStatus': 'PENDING'
            }
        }
        
        self.mock_clients_table.update_item = Mock()
        
        result = monitor_mcc_status({"client_id": "cliente1", "update_status": True})
        
        # Verificações
        self.assertEqual(result['checked_clients'], 1)
        self.assertEqual(result['updated_clients'], 1)
        self.assertEqual(result['rejected_links'], 1)
        
        # Verificar se get_link_status foi chamado
        mock_mcc_service.get_link_status.assert_called_once_with('1111111111')

def run_tests():
    """Executa todos os testes"""
    print("🧪 Executando testes do sistema MCC...")
    print("=" * 60)
    
    # Criar suite de testes
    test_suite = unittest.TestSuite()
    
    # Adicionar testes
    test_suite.addTest(unittest.makeSuite(TestGoogleAdsMCCService))
    test_suite.addTest(unittest.makeSuite(TestCreateClientIntegration))
    test_suite.addTest(unittest.makeSuite(TestMonitorMCCStatus))
    
    # Executar testes
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Resumo
    print(f"\n📊 RESUMO DOS TESTES:")
    print(f"   Testes executados: {result.testsRun}")
    print(f"   Falhas: {len(result.failures)}")
    print(f"   Erros: {len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ FALHAS:")
        for test, traceback in result.failures:
            print(f"   {test}: {traceback}")
    
    if result.errors:
        print(f"\n❌ ERROS:")
        for test, traceback in result.errors:
            print(f"   {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\n{'✅' if success else '❌'} Testes {'aprovados' if success else 'falharam'}")
    
    return success

def main():
    """Função principal"""
    print("🧪 Testador do Sistema MCC - Google Ads")
    print("=" * 60)
    
    # Verificar se estamos em ambiente de teste
    if not os.environ.get('TESTING_MODE'):
        print("⚠️  Executando em modo de teste (variáveis mockadas)")
        print("   Para testes reais, configure as variáveis de ambiente MCC")
    
    success = run_tests()
    
    if success:
        print("\n🎉 Todos os testes passaram! O sistema MCC está funcionando corretamente.")
        print("\n📋 Próximos passos:")
        print("1. Configure as variáveis de ambiente MCC reais")
        print("2. Execute: python src/scripts/manage_mcc_links.py")
        print("3. Teste com uma conta real do Google Ads")
    else:
        print("\n❌ Alguns testes falharam. Verifique os erros acima.")
    
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Testes cancelados pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado nos testes: {str(e)}")
        sys.exit(1)
