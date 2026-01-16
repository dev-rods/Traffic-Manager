import logging
import json
import traceback

def setup_logger(name, level=logging.INFO):
    """
    Configura um logger com formatação específica para o projeto
    
    Args:
        name: Nome do logger
        level: Nível de logging (padrão: INFO)
        
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evitar duplicação de handlers ao reutilizar o logger
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def log_event(logger, event, context=None, level=logging.INFO):
    """
    Loga um evento lambda com formatação amigável
    
    Args:
        logger: Logger a ser usado
        event: Evento a ser logado
        context: Contexto Lambda opcional
        level: Nível de logging para o evento
    """
    trace_id = event.get('traceId', 'no-trace-id')
    
    # Simplificar para log
    sanitized_event = {k: v for k, v in event.items() if k not in ['originalEvent']}
    
    logger.log(level, f"[traceId: {trace_id}] Evento recebido: {json.dumps(sanitized_event)}")
    
    if context:
        logger.log(level, f"[traceId: {trace_id}] Context: requestId={context.aws_request_id}, remainingTime={context.get_remaining_time_in_millis()}ms")

def log_error(logger, e, event=None, trace_id=None):
    """
    Loga um erro com o trace ID e stacktrace
    
    Args:
        logger: Logger a ser usado
        e: Exceção a ser logada
        event: Evento opcional relacionado ao erro
        trace_id: ID de trace opcional
    """
    if event and not trace_id:
        trace_id = event.get('traceId', 'no-trace-id')
    elif not trace_id:
        trace_id = 'no-trace-id'
        
    error_msg = str(e)
    stack_trace = traceback.format_exc()
    
    logger.error(f"[traceId: {trace_id}] Erro: {error_msg}")
    logger.error(f"[traceId: {trace_id}] Stack trace: {stack_trace}")
    
    if event:
        try:
            sanitized_event = {k: v for k, v in event.items() if k not in ['originalEvent']}
            logger.error(f"[traceId: {trace_id}] Evento relacionado: {json.dumps(sanitized_event)}")
        except:
            logger.error(f"[traceId: {trace_id}] Não foi possível serializar o evento relacionado")

def log_step(logger, trace_id, step_name, message, data=None, level=logging.INFO):
    """
    Loga uma etapa do processamento com o trace ID
    
    Args:
        logger: Logger a ser usado
        trace_id: ID de trace
        step_name: Nome da etapa
        message: Mensagem a ser logada
        data: Dados opcionais relacionados à etapa
        level: Nível de logging para a etapa
    """
    logger.log(level, f"[traceId: {trace_id}] [{step_name}] {message}")
    
    if data:
        try:
            if isinstance(data, str):
                logger.log(level, f"[traceId: {trace_id}] [{step_name}] Dados: {data}")
            else:
                logger.log(level, f"[traceId: {trace_id}] [{step_name}] Dados: {json.dumps(data)}")
        except:
            logger.log(level, f"[traceId: {trace_id}] [{step_name}] Não foi possível serializar os dados") 