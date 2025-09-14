# Configuração Completa de Ambiente GitLab com Múltiplas Contas (Windows)

Este projeto utiliza acesso via SSH para o GitLab. Siga as instruções a seguir para configurar o seu ambiente corretamente no Windows.

Primeiramente, gere uma nova chave SSH utilizando o terminal (Git Bash ou VSCode Terminal):

```bash
ssh-keygen -t ed25519 -C "seu-email@dominio.com"
```

Pressione ENTER para aceitar o caminho sugerido ou defina um nome específico para a chave, como `id_ed25519_traffig_manager`. Quando solicitado, pode deixar a senha em branco, apenas pressionando ENTER.

Após gerar a chave, adicione-a ao agente SSH:

```bash
eval "$(ssh-agent -s)"
ssh-add /c/Users/SeuUsuario/.ssh/id_ed25519
```

Se necessário, ative o serviço do ssh-agent:

```bash
Start-Service ssh-agent
```

Em seguida, copie o conteúdo da chave pública gerada:

```bash
cat /c/Users/SeuUsuario/.ssh/id_ed25519.pub
```

Acesse sua conta no GitLab, vá em **User Settings > SSH Keys**, cole o conteúdo da chave pública e salve.

Agora, configure o arquivo de SSH para gerenciar múltiplas contas. Acesse a pasta `C:\Users\SeuUsuario\.ssh` e crie ou edite um arquivo chamado `config` (sem extensão `.txt`). Adicione o seguinte conteúdo:

```bash
Host gitlab.com
    HostName gitlab.com
    User git
    IdentityFile C:/Users/SeuUsuario/.ssh/id_ed25519
    IdentitiesOnly yes

Host gitlab-traffig
    HostName gitlab.com
    User git
    IdentityFile C:/Users/SeuUsuario/.ssh/id_ed25519
    IdentitiesOnly yes
```

Certifique-se de que o arquivo esteja nomeado apenas como `config`, sem `.txt`. No Windows Explorer, ative a opção de visualizar extensões de arquivo para garantir isso.

Com o `config` correto, clone o repositório utilizando o host personalizado:

```bash
git clone git@gitlab-traffig:traffig-manager/infra.git
```

Antes de clonar, você pode testar a conexão SSH com:

```bash
ssh -T git@gitlab-traffig
```

Se a configuração estiver correta, a resposta será:

```
Welcome to GitLab, @seu-usuario
```

Resumo dos passos: gerar a nova chave SSH com `ssh-keygen`, adicionar a chave com `ssh-add`, cadastrar a chave pública no GitLab, configurar corretamente o arquivo `config`, testar a conexão SSH com `ssh -T`, e finalmente clonar o repositório usando `git clone` com o Host configurado.

Observações finais: sempre verifique que o arquivo `config` não tenha extensão `.txt`; prefira utilizar barras `/` no caminho mesmo em ambiente Windows; adicione novos blocos `Host` no `config` caso venha a trabalhar com mais contas no futuro; e teste a conexão SSH antes de tentar clonar ou fazer push para novos repositórios.

Com esta configuração, seu ambiente estará preparado para trabalhar com múltiplas contas GitLab de forma segura, prática e sem necessidade de ficar trocando manualmente de chave SSH.



OBS:
Na criação inicial do grupo, eu coloquei o nome do grupo como "traffig-manager" e o nome do projeto como "infra". Por isso, o host do projeto é "gitlab-traffig".

REF:
https://chatgpt.com/share/680e9b00-fb00-8008-a613-35be44e3fb84
