import { useState } from 'react';

export default function Composer({ disabled, onSend }) {
  const [value, setValue] = useState('');

  const submit = (e) => {
    e.preventDefault();
    if (!value.trim() || disabled) return;
    onSend(value);
    setValue('');
  };

  return (
    <form className="composer" onSubmit={submit}>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ou tape une commande"
        aria-label="Commande écrite"
        maxLength={500}
        autoComplete="off"
      />
      <button type="submit" disabled={disabled || !value.trim()}>Envoyer</button>
    </form>
  );
}