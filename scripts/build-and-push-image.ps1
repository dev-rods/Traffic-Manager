# Script para build e push da imagem Docker para ECR
# Uso: .\scripts\build-and-push-image.ps1 -stage dev -region us-east-1

param(
    [string]$stage = "dev",
    [string]$region = "us-east-1"
)

$ErrorActionPreference = "Stop"

# Configurações
$service = "traffic-manager-infra"
$accountId = "796000356030"
$repositoryName = "$service-$stage-lambda"
$imageUri = "$accountId.dkr.ecr.$region.amazonaws.com/$repositoryName"
$imageTag = "latest"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Build e Push Docker Image para ECR" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Service: $service" -ForegroundColor Yellow
Write-Host "Stage: $stage" -ForegroundColor Yellow
Write-Host "Region: $region" -ForegroundColor Yellow
Write-Host "Repository: $repositoryName" -ForegroundColor Yellow
Write-Host "Image URI: $imageUri" -ForegroundColor Yellow
Write-Host ""

# Verificar se Docker está instalado
Write-Host "Verificando Docker..." -ForegroundColor Green
$dockerCheck = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCheck) {
    Write-Host "ERRO: Docker não está instalado ou não está no PATH" -ForegroundColor Red
    exit 1
}
Write-Host "Docker encontrado!" -ForegroundColor Green

# Verificar se AWS CLI está instalado
Write-Host "Verificando AWS CLI..." -ForegroundColor Green
$awsCheck = Get-Command aws -ErrorAction SilentlyContinue
if (-not $awsCheck) {
    Write-Host "ERRO: AWS CLI não está instalado ou não está no PATH" -ForegroundColor Red
    exit 1
}
Write-Host "AWS CLI encontrado!" -ForegroundColor Green

# Login no ECR
Write-Host ""
Write-Host "Fazendo login no ECR..." -ForegroundColor Green
$ecrPassword = aws ecr get-login-password --region $region
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Falha ao obter senha do ECR" -ForegroundColor Red
    exit 1
}

$ecrPassword | docker login --username AWS --password-stdin $imageUri
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Falha ao fazer login no ECR" -ForegroundColor Red
    exit 1
}
Write-Host "Login realizado com sucesso!" -ForegroundColor Green

# Build da imagem
Write-Host ""
Write-Host "Fazendo build da imagem Docker..." -ForegroundColor Green
$imageNameWithTag = "${repositoryName}:${imageTag}"
$fullImageUri = "${imageUri}:${imageTag}"

docker build -t $imageNameWithTag .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Falha ao fazer build da imagem" -ForegroundColor Red
    exit 1
}

docker tag $imageNameWithTag $fullImageUri
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Falha ao fazer tag da imagem" -ForegroundColor Red
    exit 1
}
Write-Host "Build concluído com sucesso!" -ForegroundColor Green

# Push da imagem
Write-Host ""
Write-Host "Fazendo push da imagem para ECR..." -ForegroundColor Green
docker push $fullImageUri

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Falha ao fazer push da imagem" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "SUCESSO! Imagem enviada para ECR" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host "Image URI: $fullImageUri" -ForegroundColor Yellow
Write-Host ""
Write-Host "Próximos passos:" -ForegroundColor Cyan
Write-Host "1. Execute: serverless deploy --stage $stage" -ForegroundColor White
Write-Host "2. Ou teste a função Lambda diretamente no console AWS" -ForegroundColor White
