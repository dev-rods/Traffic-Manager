/**
 * Mensagem padrão da campanha de reagendamento, usada quando a clínica não
 * cadastrou um texto próprio. Vive fora do componente porque a tela de
 * configurações também a usa como placeholder - exportar função de um arquivo
 * de componente quebra o fast refresh do Vite.
 */
export function buildDefaultMessage(availableDates: string[]): string {
  const datesText = availableDates.length > 0
    ? availableDates.map((d) => {
        const [, m, day] = d.split('-')
        return `${day}/${m}`
      }).join(', ')
    : 'em breve'

  return `Oi {nome}! Tudo bem?\n\nEstamos com novas datas disponíveis para agendamento: *${datesText}*.\n\nGostaria de agendar sua sessão? Responda aqui que te ajudamos!`
}
