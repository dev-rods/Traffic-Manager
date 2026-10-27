/** Troca `{{chave}}` pelo valor; chave desconhecida fica como esta, para a
 *  pessoa ver na pre-visualizacao que digitou um nome que o sistema nao conhece. */
export function renderizaTemplate(texto: string, variaveis: Record<string, string>): string {
  return texto.replace(/\{\{\s*([\w]+)\s*\}\}/g, (todo, chave: string) => variaveis[chave] ?? todo)
}
