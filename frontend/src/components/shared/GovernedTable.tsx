import React from 'react';
import styles from './GovernedTable.module.css';

interface Column<T> {
    header: string;
    accessor: keyof T | ((item: T) => React.ReactNode);
}

interface GovernedTableProps<T> {
    data: T[];
    columns: Column<T>[];
    rowKey: keyof T;
    onRowClick?: (item: T) => void;
    errorIds?: Set<string>;
}

function GovernedTable<T>({
    data,
    columns,
    rowKey,
    onRowClick,
    errorIds
}: GovernedTableProps<T>) {
    return (
        <div className={styles.container}>
            <table className={styles.table}>
                <thead>
                    <tr>
                        {columns.map((col, idx) => (
                            <th key={idx}>{col.header}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {data.map((item) => {
                        const id = String(item[rowKey]);
                        const hasError = errorIds?.has(id);
                        return (
                            <tr
                                key={id}
                                onClick={() => onRowClick?.(item)}
                                className={hasError ? styles.rowError : ''}
                            >
                                {columns.map((col, idx) => (
                                    <td key={idx}>
                                        {typeof col.accessor === 'function'
                                            ? col.accessor(item)
                                            : (item[col.accessor] as unknown as React.ReactNode)}
                                    </td>
                                ))}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

export default GovernedTable;
