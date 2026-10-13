import { redirect } from "next/navigation";

/** Everything starts from a client project. */
export default function Home() {
  redirect("/projects");
}
