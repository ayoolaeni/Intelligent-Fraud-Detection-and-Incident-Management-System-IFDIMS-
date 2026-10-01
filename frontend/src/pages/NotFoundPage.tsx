import React from "react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <h1 className="text-2xl font-bold text-gray-900">Page not found</h1>
      <p className="mt-2 text-gray-500">The page you're looking for doesn't exist.</p>
      <Link to="/" className="mt-4 text-blue-600 hover:underline">Back to overview</Link>
    </div>
  );
}

export function ForbiddenPage() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <h1 className="text-2xl font-bold text-gray-900">Access denied</h1>
      <p className="mt-2 text-gray-500">Your role doesn't have permission to view this page.</p>
      <Link to="/" className="mt-4 text-blue-600 hover:underline">Back to overview</Link>
    </div>
  );
}
