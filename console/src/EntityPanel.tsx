import { type FormEvent, useCallback, useEffect, useState } from 'react'
import type { EntityList } from './types'

/** Pide al backend la lista de entidades y cuál está activa. */
async function fetchEntities(): Promise<EntityList> {
  const response = await fetch('/api/entities')
  return (await response.json()) as EntityList
}

/**
 * Lista, crea y carga entidades (`/api/entities`). Avisa al padre qué
 * entidad quedó activa (id y nombre), para el chat y el panel de afecto.
 */
export function EntityPanel({ onActive }: { onActive: (id: string | null, name: string | null) => void }) {
  const [list, setList] = useState<EntityList>({ ids: [], active: null, active_name: null })
  const [selected, setSelected] = useState('')
  const [form, setForm] = useState({ id: '', name: '', persona: '' })
  const [error, setError] = useState<string | null>(null)

  /** Guarda en el estado la lista recibida y avisa al padre de la entidad activa. */
  const applyList = useCallback(
    (data: EntityList) => {
      setList(data)
      setSelected((current) => current || data.active || data.ids[0] || '')
      onActive(data.active, data.active_name)
    },
    [onActive],
  )

  /** Vuelve a pedir la lista tras una acción (crear o cargar). */
  async function refresh(): Promise<void> {
    applyList(await fetchEntities())
  }

  /** Carga una entidad (emite `entity.loaded`) y la deja activa. */
  async function load(id: string): Promise<void> {
    setError(null)
    const response = await fetch(`/api/entities/${encodeURIComponent(id)}/load`, { method: 'POST' })
    if (!response.ok) {
      setError((await response.json()).detail ?? `Error ${response.status}`)
      return
    }
    setSelected(id)
    await refresh()
  }

  /** Crea una entidad con el formulario (emite `entity.created`) y la carga. */
  async function create(submit: FormEvent): Promise<void> {
    submit.preventDefault()
    setError(null)
    const response = await fetch('/api/entities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    if (!response.ok) {
      const detail = (await response.json()).detail
      // FastAPI devuelve los errores de validación como lista; se muestran en una línea.
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
      return
    }
    setForm({ id: '', name: '', persona: '' })
    await load(form.id)
  }

  // Carga inicial; después se refresca tras cada acción.
  useEffect(() => {
    fetchEntities()
      .then(applyList)
      .catch(() => setError('No se pudo contactar al backend'))
  }, [applyList])

  return (
    <section className="entity-panel">
      <div className="row">
        <select value={selected} onChange={(change) => setSelected(change.target.value)}>
          {list.ids.map((id) => (
            <option key={id} value={id}>
              {id}
              {id === list.active ? ' (activa)' : ''}
            </option>
          ))}
        </select>
        <button disabled={!selected} onClick={() => load(selected)}>
          Cargar
        </button>
      </div>
      <details>
        <summary>Crear entidad</summary>
        <form onSubmit={create} className="create-form">
          <input placeholder="id (minúsculas, p. ej. aurora)" value={form.id}
            onChange={(change) => setForm({ ...form, id: change.target.value })} required />
          <input placeholder="nombre" value={form.name}
            onChange={(change) => setForm({ ...form, name: change.target.value })} required />
          <textarea placeholder="persona (en primera persona)" value={form.persona}
            onChange={(change) => setForm({ ...form, persona: change.target.value })} />
          <button type="submit">Crear y cargar</button>
        </form>
      </details>
      {error && <p className="error">{error}</p>}
    </section>
  )
}
