"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Command,
  FolderKanban,
  LayoutGrid,
  LogOut,
  Menu,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useUser } from "./auth";
import { useNotice } from "./providers";

export function Logo() {
  return (
    <span className="brand">
      <span className="brand-symbol" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      concord<span className="brand-dot">.</span>
    </span>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const user = useUser(),
    path = usePathname(),
    router = useRouter(),
    client = useQueryClient(),
    notice = useNotice();
  const [mobile, setMobile] = useState(false);
  const quality = user.role !== "annotator";
  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
      client.clear();
      router.replace("/login");
    } catch (error) {
      notice((error as Error).message, true);
    }
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {mobile && (
        <button
          className="sidebar-backdrop"
          onClick={() => setMobile(false)}
          aria-label="Close navigation"
        />
      )}
      <aside className={`sidebar ${mobile ? "sidebar-open" : ""}`}>
        <Link href="/projects" aria-label="Concord home">
          <Logo />
        </Link>
        <button
          className="workspace-switch"
          onClick={() => notice("You’re in the Concord workspace.")}
        >
          <span className="workspace-icon">
            <Command size={17} />
          </span>
          <span>
            Concord workspace<small>TEAM WORKSPACE</small>
          </span>
          <ChevronDown size={15} />
        </button>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <Link
            className={
              path.startsWith("/projects") ? "nav-link active" : "nav-link"
            }
            href="/projects"
            onClick={() => setMobile(false)}
          >
            <FolderKanban size={19} />
            Projects
            <ChevronRight size={14} className="nav-arrow" />
          </Link>
          {quality && (
            <Link
              className={
                path.startsWith("/quality") ? "nav-link active" : "nav-link"
              }
              href="/quality"
              onClick={() => setMobile(false)}
            >
              <ShieldCheck size={19} />
              Quality overview
            </Link>
          )}
          <Link
            className={
              path.startsWith("/guide") ? "nav-link active" : "nav-link"
            }
            href="/guide"
            onClick={() => setMobile(false)}
          >
            <BookOpen size={19} />
            Field guide
          </Link>
        </nav>
        <div className="sidebar-note">
          <span className="tiny-icon">
            <Sparkles size={17} />
          </span>
          <strong>Every label matters.</strong>
          <p>
            Thoughtful annotations.
            <br />
            Models you can trust.
          </p>
          <Link href="/guide">
            Meet your workspace <ArrowUpRight size={14} />
          </Link>
        </div>
        <div className="sidebar-user">
          <span className="avatar">
            {user.name
              .split(" ")
              .map((n) => n[0])
              .join("")}
          </span>
          <span>
            <strong>{user.name}</strong>
            <small>{user.role}</small>
          </span>
          <button
            aria-label="Sign out"
            title="Sign out"
            className="icon-button"
            onClick={() => void logout()}
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-toggle"
              aria-label="Open navigation"
              onClick={() => setMobile(!mobile)}
            >
              {mobile ? <X size={20} /> : <Menu size={20} />}
            </button>
            <LayoutGrid size={16} />
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>
              {path.startsWith("/quality")
                ? "Quality overview"
                : path.startsWith("/guide")
                  ? "Field guide"
                  : "Projects"}
            </strong>
          </div>
          <div className="topbar-right">
            <span className="demo-pill">
              <span />
              Team workspace
            </span>
            <span className="avatar avatar-small">{user.name[0]}</span>
          </div>
        </header>
        <main id="main-content" className="main-content">
          {children}
        </main>
        <footer className="app-footer">
          <span>Made for thoughtful humans. Built for better models.</span>
          <span>
            Concord <span className="footer-dot">•</span> v1.0
          </span>
        </footer>
      </div>
    </div>
  );
}
