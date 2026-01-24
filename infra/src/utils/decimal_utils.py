"""
Utilitários para conversão de tipos numéricos para Decimal (compatível com DynamoDB)
"""
from decimal import Decimal
from typing import Any, Dict, List, Union


def convert_to_decimal(value: Union[int, float, str, Decimal]) -> Decimal:
    """
    Converte um valor para Decimal de forma segura.
    
    Args:
        value: Valor a ser convertido (int, float, str ou Decimal)
        
    Returns:
        Decimal: Valor convertido para Decimal
        
    Raises:
        ValueError: Se o valor não puder ser convertido para Decimal
        TypeError: Se o tipo não for suportado
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Não foi possível converter '{value}' para Decimal: {str(e)}")
    
    raise TypeError(f"Tipo não suportado para conversão: {type(value)}")


def convert_dict_to_decimal(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converte recursivamente valores numéricos em um dicionário para Decimal.
    Útil para preparar dados antes de salvar no DynamoDB.
    
    Args:
        data: Dicionário com valores que podem conter int, float ou Decimal
        
    Returns:
        Dict: Dicionário com valores numéricos convertidos para Decimal
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = convert_dict_to_decimal(value)
        elif isinstance(value, (int, float, Decimal)):
            result[key] = convert_to_decimal(value)
        elif isinstance(value, list):
            result[key] = [
                convert_dict_to_decimal(item) if isinstance(item, dict)
                else convert_to_decimal(item) if isinstance(item, (int, float, Decimal))
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def convert_decimal_to_json_serializable(obj: Any) -> Any:
    """
    Converte recursivamente valores Decimal para float para serialização JSON.
    Útil para preparar dados antes de enviar em respostas HTTP.
    
    Args:
        obj: Objeto que pode conter valores Decimal
        
    Returns:
        Objeto com valores Decimal convertidos para float
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimal_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal_to_json_serializable(item) for item in obj]
    else:
        return obj

