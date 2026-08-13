import { useState } from 'react';
import { toast } from '../components/Toast/ToastProvider';

/**
 * Manages a single image upload field: the selected File, a data-URL (or
 * existing URL) preview, and the select/clear handlers. Enforces a client-side
 * size limit before reading the file.
 *
 *   const poster = useImagePreview({ onChange: markDirty });
 *   <input type="file" onChange={poster.onSelect} />
 *   <div style={{ backgroundImage: `url(${poster.preview})` }} />
 *   <button onClick={poster.clear}>Odebrat</button>
 *
 * `setPreview` lets callers seed an existing image URL (e.g. when editing).
 */
export function useImagePreview({ maxSizeMB = 8, onChange } = {}) {
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);

  const onSelect = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    if (maxSizeMB && selected.size > maxSizeMB * 1024 * 1024) {
      toast.error(`Soubor je příliš velký (max ${maxSizeMB} MB).`, { title: 'Chyba' });
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setPreview(reader.result);
    reader.readAsDataURL(selected);
    setFile(selected);
    onChange?.();
  };

  const clear = () => {
    setPreview(null);
    setFile(null);
    onChange?.();
  };

  return { preview, file, setPreview, onSelect, clear };
}
