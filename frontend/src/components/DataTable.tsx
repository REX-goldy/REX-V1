import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "right";
  className?: string;
  render: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  getKey,
  onRowClick,
  selectedKey,
  empty = "No records.",
}: {
  columns: Column<T>[];
  rows: T[];
  getKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  selectedKey?: string;
  empty?: string;
}) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={column.align === "right" ? "num" : ""}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="empty-cell" colSpan={columns.length}>
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => {
              const key = getKey(row);
              const clickable = Boolean(onRowClick);
              return (
                <tr
                  key={key}
                  className={`${clickable ? "clickable" : ""} ${
                    selectedKey === key ? "selected" : ""
                  }`.trim()}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  tabIndex={clickable ? 0 : undefined}
                  onKeyDown={
                    onRowClick
                      ? (event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            onRowClick(row);
                          }
                        }
                      : undefined
                  }
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={`${column.align === "right" ? "num" : ""} ${
                        column.className ?? ""
                      }`.trim()}
                    >
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
