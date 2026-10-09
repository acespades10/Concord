import Link from "next/link";
export default function NotFound() {
  return (
    <div className="empty-state">
      <h1>This page wandered off.</h1>
      <Link className="button button-primary" href="/projects">
        Back to your workspace
      </Link>
    </div>
  );
}
