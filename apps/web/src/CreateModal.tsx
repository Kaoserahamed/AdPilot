import { useState, type FormEvent } from 'react';
import type { Campaign } from './data';
import Icon from './Icon';

type Props = { onClose: () => void; onCreated: (campaign: Campaign) => void };

export default function CreateModal({ onClose, onCreated }: Props) {
  const [form, setForm] = useState({ name: '', product: '', platform: 'Meta' });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onCreated({ name: form.name || 'Untitled campaign', product: form.product || 'New product', platforms: [form.platform], status: 'Draft', spend: '$0.00', updated: 'Just now' });
  };
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <section className="modal" role="dialog" aria-modal="true" aria-labelledby="create-title">
      <div className="modal-header"><div><p className="eyebrow">Campaign workspace</p><h2 id="create-title">Start a new campaign</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><Icon name="close" /></button></div>
      <p>Start with the essentials. Add audience, budget, and platform copy next.</p>
      <form onSubmit={submit}>
        <label>Campaign name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="e.g. Summer product launch" /></label>
        <label>Product or service<input required value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })} placeholder="What are you promoting?" /></label>
        <label>Primary platform<select value={form.platform} onChange={(event) => setForm({ ...form, platform: event.target.value })}><option>Meta</option><option>Google</option><option>YouTube</option><option>Meta + Google</option></select></label>
        <div className="modal-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancel</button><button className="button button-primary">Create campaign <Icon name="arrow" size={16} /></button></div>
      </form>
    </section>
  </div>;
}
