/** `HH:MM` com hora de 00 a 23 e minuto de 00 a 59. */
const HORA_VALIDA = /^([01]\d|2[0-3]):[0-5]\d$/

/**
 * O texto é um horário do dia?
 *
 * `<input type="time">` já impede a maioria das bobagens, mas devolve string
 * vazia enquanto a pessoa digita e o valor também chega de fora (o horário do
 * agendamento em edição, por exemplo). Quem decide se dá para enviar é isto.
 */
export function ehHorarioValido(time: string | null | undefined): boolean {
  return HORA_VALIDA.test(time ?? '')
}
