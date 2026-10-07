'use strict';

/**
 * Tira os AWS::Logs::LogGroup do stack sem apagar os grupos nem parar de logar.
 *
 * Por que existe: o stack de prod está em 496 dos 500 recursos que o
 * CloudFormation permite, e 78 deles são log groups - um por função. A
 * Lambda não precisa que o grupo esteja no stack: ela o cria sozinha na
 * primeira invocação, desde que a role tenha logs:CreateLogGroup (a padrão
 * tem, e as roles por função declaram explicitamente).
 *
 * Por que não `disableLogs: true`: no Serverless 3.40 isso acrescenta um Deny
 * de logs:PutLogEvents na role da função (merge-iam-templates.js) - desliga o
 * log de verdade, que é o oposto do que se quer.
 *
 * Dois modos, porque a saída tem de ser em duas etapas:
 *
 *   custom.logGroups: retain   -> DeletionPolicy: Retain em todos os grupos.
 *                                 Deploy. Nada muda em runtime.
 *   custom.logGroups: remove   -> os grupos saem do template (e o DependsOn
 *                                 das funções que apontava para eles). Como o
 *                                 deploy anterior marcou Retain, o CloudFormation
 *                                 desvincula os grupos em vez de apagá-los. O
 *                                 histórico fica, a Lambda continua escrevendo.
 *
 * Pular a etapa `retain` APAGA os 78 grupos no deploy - é por isso que o modo
 * `remove` recusa rodar se encontrar algum grupo sem Retain no stack atual não
 * dá para checar daqui; a ordem é responsabilidade de quem muda a flag, e está
 * documentada em serverless.yml.
 *
 * O que fica fora do stack a partir daí: retenção dos logs (hoje já é "nunca
 * expira" para todos; passa a ser gerida por `aws logs put-retention-policy`)
 * e a limpeza do grupo quando uma função é apagada (fica órfão, custa centavos).
 */
class LogGroupsForaDoStack {
  constructor(serverless) {
    this.serverless = serverless;
    this.hooks = {
      'before:package:finalize': () => this.aplica(),
    };
  }

  aplica() {
    const modo = (this.serverless.service.custom || {}).logGroups;
    if (!modo) return;
    if (!['retain', 'remove'].includes(modo)) {
      throw new this.serverless.classes.Error(
        `custom.logGroups deve ser "retain" ou "remove", veio "${modo}"`
      );
    }

    const template = this.serverless.service.provider.compiledCloudFormationTemplate;
    const recursos = template.Resources;
    const grupos = Object.keys(recursos).filter(
      (id) => recursos[id].Type === 'AWS::Logs::LogGroup'
    );

    if (modo === 'retain') {
      grupos.forEach((id) => {
        recursos[id].DeletionPolicy = 'Retain';
        recursos[id].UpdateReplacePolicy = 'Retain';
      });
      this.serverless.cli.log(`[log-groups] ${grupos.length} log groups com DeletionPolicy: Retain`);
      return;
    }

    const conjunto = new Set(grupos);
    grupos.forEach((id) => delete recursos[id]);
    let dependencias = 0;
    Object.values(recursos).forEach((recurso) => {
      if (!Array.isArray(recurso.DependsOn)) return;
      const antes = recurso.DependsOn.length;
      recurso.DependsOn = recurso.DependsOn.filter((dep) => !conjunto.has(dep));
      dependencias += antes - recurso.DependsOn.length;
      if (recurso.DependsOn.length === 0) delete recurso.DependsOn;
    });
    this.serverless.cli.log(
      `[log-groups] ${grupos.length} log groups fora do stack, ${dependencias} DependsOn removidos`
    );
  }
}

module.exports = LogGroupsForaDoStack;
