import React from "react";

export function LoadingRow({ colSpan }: { colSpan: number }) {
  return (
    <tr>
      <td colSpan={colSpan} className="p-6 text-center text-sm text-gray-400">
        Loading...
      </td>
    </tr>
  );
}

export function EmptyRow({ colSpan, message = "No results found" }: { colSpan: number; message?: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="p-6 text-center text-sm text-gray-400">
        {message}
      </td>
    </tr>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{message}</div>;
}

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between border-t border-gray-200 px-2 py-3 text-sm text-gray-600">
      <span>
        Page {page} of {totalPages} ({total} total)
      </span>
      <div className="flex gap-2">
        <button
          className="rounded border px-2 py-1 disabled:opacity-40"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          Previous
        </button>
        <button
          className="rounded border px-2 py-1 disabled:opacity-40"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

export function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-gray-200 bg-white p-4 shadow-sm">
      {title && <h3 className="mb-3 text-sm font-semibold text-gray-700">{title}</h3>}
      {children}
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded bg-white p-5 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
