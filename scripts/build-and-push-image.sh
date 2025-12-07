#!/bin/bash
# Script para build e push da imagem Docker para ECR
# Uso: ./scripts/build-and-push-image.sh [stage] [region]

set -e

# Configurações padrão
STAGE=${1:-dev}
REGION=${2:-us-east-1}
SERVICE="traffic-manager-infra"
ACCOUNT_ID="796000356030"
REPOSITORY_NAME="${SERVICE}-${STAGE}-lambda"
IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY_NAME}"
IMAGE_TAG="latest"

echo "========================================="
echo "Build e Push Docker Image para ECR"
echo "========================================="
echo "Service: $SERVICE"
echo "Stage: $STAGE"
echo "Region: $REGION"
echo "Repository: $REPOSITORY_NAME"
echo "Image URI: $IMAGE_URI"
echo ""

# Verificar se Docker está instalado
echo "Verificando Docker..."
if ! command -v docker &> /dev/null; then
    echo "ERRO: Docker não está instalado ou não está no PATH"
    exit 1
fi
echo "Docker encontrado!"

# Verificar se AWS CLI está instalado
echo "Verificando AWS CLI..."
if ! command -v aws &> /dev/null; then
    echo "ERRO: AWS CLI não está instalado ou não está no PATH"
    exit 1
fi
echo "AWS CLI encontrado!"

# Login no ECR
echo ""
echo "Fazendo login no ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $IMAGE_URI

# Build da imagem
echo ""
echo "Fazendo build da imagem Docker..."
docker build -t $REPOSITORY_NAME:$IMAGE_TAG .
docker tag $REPOSITORY_NAME:$IMAGE_TAG $IMAGE_URI:$IMAGE_TAG

# Push da imagem
echo ""
echo "Fazendo push da imagem para ECR..."
docker push $IMAGE_URI:$IMAGE_TAG

echo ""
echo "========================================="
echo "SUCESSO! Imagem enviada para ECR"
echo "========================================="
echo "Image URI: $IMAGE_URI:$IMAGE_TAG"
echo ""
echo "Próximos passos:"
echo "1. Execute: serverless deploy --stage $STAGE"
echo "2. Ou teste a função Lambda diretamente no console AWS"
