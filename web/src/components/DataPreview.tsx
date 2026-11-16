import type { DatasetFile } from '../api/types'
import { fmt } from '../lib/format'

export function DataPreview({ file }: { file: DatasetFile }) {
  return (
    <>
      <p className="dmeta">{`${fmt(file.rows)} rows · ${file.columns.length} columns`}</p>
      <div className="dscroll">
        <table className="dtab">
          <thead>
            <tr>
              {file.columns.map((c) => (
                <th key={c.name}>
                  {c.name}
                  <span className="dt">{c.dtype}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {file.preview.slice(0, 8).map((r, i) => (
              <tr key={i}>
                {file.columns.map((c, j) => (
                  <td key={c.name} className={c.dtype === 'text' ? '' : 'num'}>
                    {r[j] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
