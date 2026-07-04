import { useCallback, useEffect, useState } from "react";
import { deleteDocument, DocumentSummary, listDocuments, uploadDocument } from "../lib/api";
import { getIdToken } from "../lib/firebase";

export default function AdminDashboard() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadStatus, setUploadStatus] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const docs = await listDocuments(getIdToken);
      setDocuments(docs);
    } catch {
      setError("Failed to load documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus(`Uploading ${file.name}…`);
    try {
      const result = await uploadDocument(file, getIdToken);
      setUploadStatus(
        `Ingested "${result.filename}": ${result.chunks_created} chunks, ` +
          `${result.entities_extracted} entities, ${result.relationships_extracted} relationships.`
      );
      await refresh();
    } catch {
      setUploadStatus("Upload failed. Please try again.");
    } finally {
      e.target.value = "";
    }
  }

  async function handleDelete(doc: DocumentSummary) {
    if (!confirm(`Delete "${doc.filename}"? This removes its chunks, graph facts, and file.`)) return;
    try {
      await deleteDocument(doc.id, getIdToken);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch {
      setError(`Failed to delete "${doc.filename}".`);
    }
  }

  return (
    <div className="admin-dashboard">
      <div className="admin-toolbar">
        <label className="upload-button">
          Upload PDF
          <input type="file" accept="application/pdf" onChange={handleUpload} hidden />
        </label>
        <button onClick={refresh} className="secondary-button">
          Refresh
        </button>
        {uploadStatus && <span className="upload-status">{uploadStatus}</span>}
      </div>

      {error && <p className="error-text">{error}</p>}

      {loading ? (
        <p>Loading documents…</p>
      ) : documents.length === 0 ? (
        <p>No documents uploaded yet.</p>
      ) : (
        <table className="doc-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Status</th>
              <th>Chunks</th>
              <th>Entities</th>
              <th>Relationships</th>
              <th>Uploaded</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id}>
                <td>{doc.filename}</td>
                <td>
                  <span className={`status-badge status-${doc.status}`}>{doc.status}</span>
                </td>
                <td>{doc.chunks_created}</td>
                <td>{doc.entities_extracted}</td>
                <td>{doc.relationships_extracted}</td>
                <td>{new Date(doc.created_at).toLocaleString()}</td>
                <td>
                  <button className="danger-button" onClick={() => handleDelete(doc)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
