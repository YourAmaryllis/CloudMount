import {
  Cloud,
  KeyRound,
  MonitorSmartphone,
  LayoutGrid,
  ShieldCheck,
  Globe2,
  RotateCw,
  FileCode2,
  HardDrive,
  Wifi,
  FolderSync,
  type LucideIcon,
} from "lucide-react";

const GITHUB_URL = "https://github.com/YourAmaryllis/CloudMount";

type Feature = {
  icon: LucideIcon;
  title: string;
  description: string;
};

const shippedFeatures: Feature[] = [
  {
    icon: Cloud,
    title: "Mount cloud storage as a local drive",
    description:
      "FUSE (rclone mount) and NFS (rclone nfsmount) on macOS, rclone mount + WinFsp on Windows — your bucket shows up like any other folder.",
  },
  {
    icon: LayoutGrid,
    title: "Hosts & mounts in a local web UI",
    description:
      "Add remotes, pick paths, mount/unmount — served from 127.0.0.1:8765, nothing reachable from the network.",
  },
  {
    icon: KeyRound,
    title: "Secrets in Keychain / Credential Manager",
    description:
      "Static keys and AWS profile credentials never touch a plaintext config file on disk.",
  },
  {
    icon: Globe2,
    title: "AWS profile & SSO, not just static keys",
    description:
      "Use a named profile from ~/.aws — IAM user, SSO, or Roles Anywhere via credential_process — same as the AWS CLI.",
  },
  {
    icon: MonitorSmartphone,
    title: "Tray icon on both platforms",
    description:
      "Menu bar on macOS, system tray on Windows — mount, unmount, and check status without opening the web UI.",
  },
  {
    icon: HardDrive,
    title: "Official rclone, not a fork",
    description:
      "Downloaded straight from rclone on first setup — every backend rclone supports is available, tested so far on Wasabi and Proton Drive.",
  },
];

const roadmapFeatures: Feature[] = [
  {
    icon: RotateCw,
    title: "Auto-mount on login",
    description:
      "Remount everything after a reboot without clicking through the UI — per-mount toggle, skips what's already up.",
  },
  {
    icon: Wifi,
    title: "AWS session recovery",
    description:
      "SSO sessions expire mid-day. Detect the dead mount and offer a one-click AWS login + remount, only on failure — no proactive polling.",
  },
  {
    icon: ShieldCheck,
    title: "Read-only mounts",
    description:
      "A per-mount checkbox to pass rclone --read-only, for the \"cloud storage as a safe reference copy\" case.",
  },
  {
    icon: FileCode2,
    title: "Import from an existing rclone.conf",
    description:
      "Already use rclone directly? Map your remotes to CloudMount hosts instead of re-entering everything by hand.",
  },
];

const useCases = [
  {
    icon: HardDrive,
    title: "Cloud storage as a local Finder/Explorer folder",
    description:
      "Drag files in and out like any local drive — no browser upload dialog, no separate sync client.",
  },
  {
    icon: KeyRound,
    title: "AWS SSO without juggling temporary credentials",
    description:
      "Point a host at your named profile; CloudMount runs aws sso login only after a failed connection, not on a timer.",
  },
  {
    icon: Cloud,
    title: "Proton Drive, mounted",
    description:
      "One of the tested backends — set it up once from the web UI, then treat it like local disk.",
  },
  {
    icon: FolderSync,
    title: "Storage you can swap without changing your workflow",
    description:
      "Any rclone backend works the same way in CloudMount — move providers without relearning a new app.",
  },
];

const faqs = [
  {
    question: "Is it actually free?",
    answer:
      "Yes — MIT licensed, no trial, no license key, no paywalled features. Build it from source or grab a signed release from GitHub.",
  },
  {
    question: "Does it collect any data?",
    answer:
      "No. Everything runs locally — mounts, the web UI, and credential storage. There's no account, no analytics, no telemetry.",
  },
  {
    question: "What platforms does it support?",
    answer:
      "macOS 14 (Sonoma) and later, and Windows with WinFsp installed. Same feature set, native tray icon on both.",
  },
  {
    question: "How is this different from just using rclone directly?",
    answer:
      "A tray icon, a web UI for hosts and mounts instead of hand-editing rclone.conf, Keychain/Credential Manager-backed secrets, and AWS SSO handling — rclone does the heavy lifting underneath, CloudMount is the part you actually interact with.",
  },
  {
    question: "Is the macOS build signed and notarized?",
    answer:
      "Check the release notes for the version you're downloading — recent releases are signed with a Developer ID certificate and notarized, so Gatekeeper opens them with no warning.",
  },
];

function FeatureCard({ feature, muted = false }: { feature: Feature; muted?: boolean }) {
  const Icon = feature.icon;
  return (
    <div
      className={`rounded-2xl border p-6 ${
        muted
          ? "border-black/10 bg-black/[.02] dark:border-white/10 dark:bg-white/[.03]"
          : "border-black/10 dark:border-white/10"
      }`}
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-foreground/[.06] dark:bg-foreground/[.1]">
        <Icon className="h-4.5 w-4.5" strokeWidth={1.75} />
      </div>
      <h3 className="mt-4 font-medium">{feature.title}</h3>
      <p className="mt-2 text-sm text-foreground/70">{feature.description}</p>
    </div>
  );
}

export default function Home() {
  return (
    <div className="flex flex-col">
      <header className="flex items-center justify-between px-6 py-5 sm:px-10">
        <span className="text-lg font-semibold tracking-tight">CloudMount</span>
        <a
          href={GITHUB_URL}
          className="rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition hover:opacity-90"
        >
          GitHub
        </a>
      </header>

      <section className="mx-auto flex max-w-3xl flex-col items-center gap-6 px-6 py-20 text-center sm:py-28">
        <span className="rounded-full border border-black/10 px-3 py-1 text-xs text-foreground/60 dark:border-white/15">
          Free &amp; open source · macOS and Windows
        </span>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-6xl">
          Your cloud storage, mounted like a local drive
        </h1>
        <p className="max-w-xl text-balance text-base text-foreground/70 sm:text-lg">
          CloudMount turns any rclone backend — Wasabi, S3, Proton Drive, and
          more — into a folder on your Mac or PC. Add a host, pick a path,
          mount it. No account, no subscription, no vendor lock-in.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <a
            href="#open-source"
            className="rounded-full bg-foreground px-6 py-3 text-sm font-medium text-background transition hover:opacity-90"
          >
            Download
          </a>
          <a
            href="#features"
            className="rounded-full border border-black/10 px-6 py-3 text-sm font-medium transition hover:bg-black/5 dark:border-white/15 dark:hover:bg-white/10"
          >
            See what it does
          </a>
        </div>
      </section>

      <section className="mx-auto w-full max-w-3xl px-6 pb-16 text-center sm:pb-20">
        <p className="text-balance text-lg text-foreground/60 sm:text-xl">
          rclone is the engine <span className="text-foreground">underneath</span>{" "}
          — powerful, but a config file and a terminal away from feeling like
          a real drive. CloudMount is the tray icon, the web UI, and the
          Keychain-backed secrets that make it one.
        </p>
      </section>

      <section id="features" className="mx-auto w-full max-w-5xl px-6 py-16 sm:py-20">
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Everything you need, nothing you don&rsquo;t
        </h2>
        <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {shippedFeatures.map((feature) => (
            <FeatureCard key={feature.title} feature={feature} />
          ))}
        </div>
      </section>

      <section className="mx-auto w-full max-w-5xl px-6 py-16 sm:py-20">
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          On the roadmap
        </h2>
        <p className="mt-2 text-sm text-foreground/60">
          Being upfront: these aren&rsquo;t built yet. Tracked in the open in{" "}
          <a
            href={`${GITHUB_URL}/blob/main/docs/FUTURE.md`}
            className="underline underline-offset-2 hover:text-foreground"
          >
            docs/FUTURE.md
          </a>
          .
        </p>
        <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2">
          {roadmapFeatures.map((feature) => (
            <FeatureCard key={feature.title} feature={feature} muted />
          ))}
        </div>
      </section>

      <section className="mx-auto w-full max-w-5xl px-6 py-16 sm:py-20">
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Built for how you actually work
        </h2>
        <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2">
          {useCases.map((useCase) => {
            const Icon = useCase.icon;
            return (
              <div key={useCase.title} className="flex gap-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-foreground/[.06] dark:bg-foreground/[.1]">
                  <Icon className="h-4.5 w-4.5" strokeWidth={1.75} />
                </div>
                <div>
                  <h3 className="font-medium">{useCase.title}</h3>
                  <p className="mt-1 text-sm text-foreground/70">
                    {useCase.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section
        id="open-source"
        className="mx-auto w-full max-w-5xl px-6 py-16 sm:py-20"
      >
        <div className="rounded-2xl border border-black/10 p-8 dark:border-white/10">
          <div className="flex flex-col items-start gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                Free. Open source. Yours.
              </h2>
              <p className="mt-3 max-w-xl text-sm text-foreground/70">
                CloudMount is MIT-licensed and built in the open. No trial,
                no license key, no paywalled features — clone it, build it,
                or grab a release. Everything runs locally; nothing phones
                home.
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-3">
              <a
                href={GITHUB_URL}
                className="rounded-full bg-foreground px-6 py-3 text-sm font-medium text-background transition hover:opacity-90"
              >
                View on GitHub
              </a>
              <a
                href={`${GITHUB_URL}/releases/latest`}
                className="rounded-full border border-black/10 px-6 py-3 text-sm font-medium transition hover:bg-black/5 dark:border-white/15 dark:hover:bg-white/10"
              >
                Latest release
              </a>
            </div>
          </div>

          <div className="mt-8 overflow-x-auto">
            <table className="w-full min-w-[420px] text-left text-sm">
              <thead>
                <tr className="border-b border-black/10 text-foreground/60 dark:border-white/10">
                  <th className="py-2 pr-4 font-medium">Asset</th>
                  <th className="py-2 font-medium">Platform</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/10 dark:divide-white/10">
                <tr>
                  <td className="py-3 pr-4 font-mono text-xs">
                    CloudMount-x.y.z.dmg
                  </td>
                  <td className="py-3 text-foreground/70">
                    macOS 14+ (Apple Silicon &amp; Intel)
                  </td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-mono text-xs">
                    CloudMount-x.y.z-windows-setup.exe
                  </td>
                  <td className="py-3 text-foreground/70">
                    Windows installer
                  </td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-mono text-xs">
                    CloudMount-x.y.z-windows.zip
                  </td>
                  <td className="py-3 text-foreground/70">
                    Windows portable
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-3xl px-6 py-16 sm:py-20">
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Questions? We&rsquo;ve got answers.
        </h2>
        <div className="mt-8 divide-y divide-black/10 dark:divide-white/10">
          {faqs.map((faq) => (
            <div key={faq.question} className="py-5">
              <h3 className="font-medium">{faq.question}</h3>
              <p className="mt-2 text-sm text-foreground/70">{faq.answer}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="mx-auto w-full max-w-5xl px-6 py-10 text-xs text-foreground/50">
        © {new Date().getFullYear()} CloudMount. MIT licensed.
      </footer>
    </div>
  );
}
