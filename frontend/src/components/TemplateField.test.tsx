import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { TemplateField } from './TemplateField'
import { renderizaTemplate } from '@/utils/renderizaTemplate'

const mutate = vi.fn()
const mockUseTemplate = vi.fn()
vi.mock('@/hooks/useTemplates', () => ({
  useTemplate: (...a: unknown[]) => mockUseTemplate(...a),
  useSalvaTemplate: () => ({ mutate, isPending: false, isError: false }),
}))

const PADRAO = 'Oi {{nome}}! Sessão de {{areas}} às {{hora}}.'
const EXEMPLO = { nome: 'Maria', areas: 'Axilas', hora: '09:00' }

function monta(template: { id: string; content: string } | null) {
  mockUseTemplate.mockReturnValue({ data: template, isLoading: false, isError: false })
  return render(<TemplateField templateKey="LEMBRETE_SESSAO" label="Texto" padrao={PADRAO} exemplo={EXEMPLO} />)
}

describe('renderizaTemplate', () => {
  it('troca as variaveis e deixa a desconhecida visivel', () => {
    expect(renderizaTemplate('Oi {{nome}}, {{xpto}}', { nome: 'Ana' })).toBe('Oi Ana, {{xpto}}')
  })
})

describe('TemplateField', () => {
  beforeEach(() => {
    mutate.mockReset()
  })

  it('sem texto gravado, mostra o padrao na previa e nao deixa salvar', () => {
    monta(null)
    expect(screen.getByTestId('preview')).toHaveTextContent('Oi Maria! Sessão de Axilas às 09:00.')
    expect(screen.getByRole('button', { name: 'Salvar texto' })).toBeDisabled()
  })

  it('editar atualiza a previa e salvar cria quando nao ha linha', () => {
    monta(null)
    fireEvent.change(screen.getByLabelText('Texto'), { target: { value: 'Olá {{nome}}' } })
    expect(screen.getByTestId('preview')).toHaveTextContent('Olá Maria')
    fireEvent.click(screen.getByRole('button', { name: 'Salvar texto' }))
    expect(mutate).toHaveBeenCalledWith({ templateId: null, content: 'Olá {{nome}}' }, expect.anything())
  })

  it('com linha gravada, salvar atualiza pelo id', () => {
    monta({ id: 't1', content: 'Texto da clínica {{nome}}' })
    expect(screen.getByLabelText('Texto')).toHaveValue('Texto da clínica {{nome}}')
    fireEvent.change(screen.getByLabelText('Texto'), { target: { value: 'Novo {{nome}}' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar texto' }))
    expect(mutate).toHaveBeenCalledWith({ templateId: 't1', content: 'Novo {{nome}}' }, expect.anything())
  })

  it('apagar tudo salva o padrao, nao texto vazio', () => {
    monta({ id: 't1', content: 'Algo' })
    fireEvent.change(screen.getByLabelText('Texto'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar texto' }))
    expect(mutate).toHaveBeenCalledWith({ templateId: 't1', content: PADRAO }, expect.anything())
  })
})
