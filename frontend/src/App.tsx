import { useEffect, useState } from "react";
import { User } from "firebase/auth";
import { signIn, subscribeToAuth, getIdToken } from "./lib/firebase";
import { getMe } from "./lib/api";
import ChatPanel from "./components/ChatPanel";
import AdminDashboard from "./components/AdminDashboard";
import "./index.css";

type Role = "loading" | "user" | "admin";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [role, setRole] = useState<Role>("loading");
  const [view, setView] = useState<"chat" | "admin">("chat");

  useEffect(() => subscribeToAuth(setUser), []);

  useEffect(() => {
    if (!user) {
      setRole("loading");
      return;
    }
    setRole("loading");
    // Force-refresh the token once so a freshly-granted admin claim is picked up.
    getIdToken(true)
      .then(() => getMe(getIdToken))
      .then((me) => {
        const nextRole = me.is_admin ? "admin" : "user";
        setRole(nextRole);
        setView(nextRole === "admin" ? "admin" : "chat");
      })
      .catch(() => setRole("user"));
  }, [user]);

  if (!user) {
    return (
      <div className="login-screen">
        <h1>GraphRAG Platform</h1>
        <button onClick={() => signIn()}>Sign in with Google</button>
      </div>
    );
  }

  if (role === "loading") {
    return (
      <div className="login-screen">
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header>
        <h1>GraphRAG Platform</h1>
        <div className="header-right">
          {role === "admin" && (
            <div className="view-toggle">
              <button
                className={view === "chat" ? "active" : ""}
                onClick={() => setView("chat")}
              >
                Chat
              </button>
              <button
                className={view === "admin" ? "active" : ""}
                onClick={() => setView("admin")}
              >
                Admin
              </button>
            </div>
          )}
          <span>{user.email}</span>
        </div>
      </header>
      <main>{view === "admin" && role === "admin" ? <AdminDashboard /> : <ChatPanel />}</main>
    </div>
  );
}

