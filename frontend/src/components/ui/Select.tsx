import { useId, type SelectHTMLAttributes } from 'react';
import { cx } from './cx';

/**
 * Select nativo com rótulo.
 *
 * Nativo, e não uma lista custom: teclado, leitor de tela e o menu do sistema
 * operacional já funcionam. Um combobox próprio só se aparecer um requisito
 * que o nativo não atenda.
 */
export interface SelectOption {
  readonly value: string;
  readonly label: string;
  /** Opções com o mesmo `group` viram um `<optgroup>`, na ordem em que
   * aparecem. É como o diálogo de alocação separa squads de pessoas sem
   * precisar de dois controles. */
  readonly group?: string;
}

export interface SelectProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  readonly label: string;
  readonly options: readonly SelectOption[];
  /** Primeira opção neutra, para filtro que aceita "todos". */
  readonly placeholder?: string;
}

export function Select({
  label,
  options,
  placeholder,
  className,
  id,
  ...props
}: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  return (
    <span className={cx('inline-flex flex-col gap-1', className)}>
      <label htmlFor={selectId} className="text-12 text-text-subtle">
        {label}
      </label>
      <select
        id={selectId}
        {...props}
        className={cx(
          'h-8 rounded-sm border border-border-strong bg-surface px-2 text-14 text-text',
          'hover:border-primary focus:border-primary disabled:text-text-disabled',
        )}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {groupOptions(options).map(([group, entries]) =>
          group === null ? (
            entries.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))
          ) : (
            <optgroup key={group} label={group}>
              {entries.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </optgroup>
          ),
        )}
      </select>
    </span>
  );
}

/** Agrupa preservando a ordem de chegada; sem `group`, uma fatia solta. */
function groupOptions(
  options: readonly SelectOption[],
): Array<[string | null, SelectOption[]]> {
  const groups: Array<[string | null, SelectOption[]]> = [];
  for (const option of options) {
    const key = option.group ?? null;
    const last = groups[groups.length - 1];
    if (last && last[0] === key) last[1].push(option);
    else groups.push([key, [option]]);
  }
  return groups;
}
