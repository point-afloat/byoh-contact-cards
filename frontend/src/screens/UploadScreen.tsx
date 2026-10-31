import { Camera, ImageUp } from "lucide-react";
import { type DragEvent, useRef, useState } from "react";
import { ApiClientError } from "@/api/client";
import { useCreateSession } from "@/api/hooks";
import { ErrorAlert, Spinner } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { strings } from "@/strings";

const ACCEPTED_TYPES = ["image/jpeg", "image/png"];

type Props = {
  onCreated: (sessionId: string) => void;
  /** Shown above the form, e.g. when a previous session has expired. */
  notice?: string;
};

export function UploadScreen({ onCreated, notice }: Props) {
  const create = useCreateSession();
  const cameraInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const busy = create.isPending;
  const error =
    localError ?? (create.error instanceof ApiClientError ? create.error.message : null) ??
    (create.error ? strings.genericError : null);

  function submit(file: File | undefined) {
    if (!file || busy) return;
    if (!ACCEPTED_TYPES.includes(file.type)) {
      create.reset();
      setLocalError(strings.upload.wrongType);
      return;
    }
    setLocalError(null);
    create.mutate(file, { onSuccess: (session) => onCreated(session.id) });
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    submit(event.dataTransfer.files[0]);
  }

  return (
    <section aria-labelledby="upload-heading" aria-busy={busy} className="flex flex-col gap-4">
      <h2 id="upload-heading" className="text-xl font-semibold">
        {strings.upload.heading}
      </h2>

      {notice && <ErrorAlert>{notice}</ErrorAlert>}
      {error && <ErrorAlert>{error}</ErrorAlert>}

      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        data-testid="drop-zone"
        className={cn(
          "flex flex-col items-center gap-4 rounded-xl border-2 border-dashed border-border p-8 text-center",
          dragging && "border-primary bg-muted",
        )}
      >
        {busy ? (
          <p role="status" className="flex items-center gap-3 text-lg">
            <Spinner />
            {strings.upload.reading}
          </p>
        ) : (
          <>
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
              <Button onClick={() => cameraInput.current?.click()} disabled={busy}>
                <Camera aria-hidden="true" className="size-5" />
                {strings.upload.takePhoto}
              </Button>
              <Button variant="outline" onClick={() => fileInput.current?.click()} disabled={busy}>
                <ImageUp aria-hidden="true" className="size-5" />
                {strings.upload.chooseFile}
              </Button>
            </div>
            <p className="hidden text-muted-foreground sm:block">{strings.upload.dropHint}</p>
            <p className="text-sm text-muted-foreground">{strings.upload.formatHint}</p>
          </>
        )}
      </div>

      {/* The camera input opens the camera on phones; the file input opens the picker. */}
      <input
        ref={cameraInput}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        aria-label={strings.upload.takePhoto}
        disabled={busy}
        onChange={(event) => {
          submit(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <input
        ref={fileInput}
        type="file"
        accept="image/jpeg,image/png"
        hidden
        aria-label={strings.upload.chooseFile}
        disabled={busy}
        onChange={(event) => {
          submit(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
    </section>
  );
}
