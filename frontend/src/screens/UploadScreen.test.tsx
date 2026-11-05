import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api, ApiClientError } from "@/api/client";
import type { SessionOut } from "@/api/types";
import { strings } from "@/strings";
import { UploadScreen } from "./UploadScreen";

// The upload request itself (multipart body, error parsing) is covered in api/client.test.ts.
// Here the API is stubbed so the tests are about what the user sees.
const session: SessionOut = {
  id: "abc123",
  contact: null,
  warnings: [],
  sent: false,
  errors: {},
};
const jpeg = () => new File(["jpeg"], "card.jpg", { type: "image/jpeg" });

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup(props: { notice?: string } = {}) {
  const onCreated = vi.fn();
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { mutations: { retry: false } } })
      }
    >
      <UploadScreen onCreated={onCreated} {...props} />
    </QueryClientProvider>,
  );
  return { onCreated };
}

const chooseFileInput = () =>
  screen.getByLabelText(strings.upload.chooseFile, { selector: "input" });
const cameraInput = () =>
  screen.getByLabelText(strings.upload.takePhoto, { selector: "input" });

afterEach(() => vi.restoreAllMocks());

test("an accepted image is uploaded and the session id is handed on", async () => {
  const create = vi.spyOn(api, "createSession").mockResolvedValue(session);
  const { onCreated } = setup();
  const file = jpeg();
  await userEvent.upload(chooseFileInput(), file);
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith("abc123"));
  expect(create).toHaveBeenCalledWith(file);
});

test("the camera input asks the phone camera and the picker only offers JPEG and PNG", () => {
  setup();
  expect(cameraInput()).toHaveAttribute("capture", "environment");
  expect(chooseFileInput()).toHaveAttribute("accept", "image/jpeg,image/png");
});

test("a dropped image is uploaded", async () => {
  vi.spyOn(api, "createSession").mockResolvedValue(session);
  const { onCreated } = setup();
  fireEvent.drop(screen.getByTestId("drop-zone"), {
    dataTransfer: { files: [jpeg()] },
  });
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith("abc123"));
});

test("a PDF is rejected immediately with the accepted formats and nothing is uploaded", () => {
  const create = vi.spyOn(api, "createSession").mockResolvedValue(session);
  const { onCreated } = setup();
  const pdf = new File(["%PDF"], "card.pdf", { type: "application/pdf" });
  fireEvent.drop(screen.getByTestId("drop-zone"), {
    dataTransfer: { files: [pdf] },
  });

  expect(screen.getByRole("alert")).toHaveTextContent("JPEG and PNG");
  expect(create).not.toHaveBeenCalled();
  expect(onCreated).not.toHaveBeenCalled();
});

test("an oversized file shows the server's message with the limit", async () => {
  vi.spyOn(api, "createSession").mockRejectedValue(
    new ApiClientError(
      413,
      "file_too_large",
      "The file is too large. The limit is 10 MB.",
    ),
  );
  const { onCreated } = setup();
  await userEvent.upload(chooseFileInput(), jpeg());
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The limit is 10 MB.",
  );
  expect(onCreated).not.toHaveBeenCalled();
});

test("an unexpected failure falls back to a generic message", async () => {
  vi.spyOn(api, "createSession").mockRejectedValue(new Error("boom"));
  setup();
  await userEvent.upload(chooseFileInput(), jpeg());
  expect(await screen.findByRole("alert")).toHaveTextContent(
    strings.genericError,
  );
});

test("while extracting, a progress message shows and the inputs are disabled", async () => {
  const pending = deferred<SessionOut>();
  vi.spyOn(api, "createSession").mockReturnValue(pending.promise);
  const { onCreated } = setup();
  await userEvent.upload(chooseFileInput(), jpeg());

  expect(await screen.findByRole("status")).toHaveTextContent(
    strings.upload.reading,
  );
  expect(chooseFileInput()).toBeDisabled();
  expect(cameraInput()).toBeDisabled();
  expect(
    screen.getByRole("region", { name: strings.upload.heading }),
  ).toHaveAttribute("aria-busy", "true");

  pending.resolve(session);
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith("abc123"));
});

test("a drop while busy does not start a second upload", async () => {
  const pending = deferred<SessionOut>();
  const create = vi
    .spyOn(api, "createSession")
    .mockReturnValue(pending.promise);
  const { onCreated } = setup();
  await userEvent.upload(chooseFileInput(), jpeg());
  await screen.findByRole("status");

  fireEvent.drop(screen.getByTestId("drop-zone"), {
    dataTransfer: { files: [jpeg()] },
  });
  pending.resolve(session);

  await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
  expect(create).toHaveBeenCalledTimes(1);
});

test("a notice, such as an expired session, is announced", () => {
  setup({
    notice: "This review session has expired. Please scan the card again.",
  });
  expect(screen.getByRole("alert")).toHaveTextContent("scan the card again");
});

test("the accepted formats are always stated", () => {
  setup();
  expect(screen.getByText(strings.upload.formatHint)).toBeInTheDocument();
});
