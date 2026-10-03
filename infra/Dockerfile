# Dockerfile para AWS Lambda com Python 3.9
# google-ads 31.x aceita >=3.9, mas o google-api-core já avisa que 3.9 não
# recebe mais atualizações. Subir a base para 3.11+ é dívida conhecida.
FROM public.ecr.aws/lambda/python:3.9

# Copiar requirements e instalar dependências
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt -t ${LAMBDA_TASK_ROOT}

# Copiar código da aplicação
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Definir o handler padrão (será sobrescrito por cada função via command)
CMD [ "src.functions.campaign.orchestrator.handler" ]
