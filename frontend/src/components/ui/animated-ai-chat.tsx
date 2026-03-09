"use client";

import { useEffect, useRef, useState } from "react";
import {
	Paperclip,
	SendIcon,
	LoaderIcon,
	XIcon,
	FileText,
	Database,
	Search,
	MessageSquare,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface AttachmentItem {
	id: string;
	name: string;
	status: "uploading" | "ready" | "failed";
	sourceId?: string;
	error?: string;
}

interface ChatTurn {
	question: string;
	answer: string;
	sources: string[];
}

function createId() {
	if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
		return crypto.randomUUID();
	}
	return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function getErrorMessage(error: unknown) {
	if (error instanceof Error) return error.message;
	return "Request failed";
}

async function parseError(response: Response) {
	try {
		const body = await response.json();
		if (body?.detail && typeof body.detail === "string") return body.detail;
	} catch {
		// no-op
	}
	return `Request failed (${response.status})`;
}

export function AnimatedAIChat() {
	const apiBase = (
		import.meta.env.VITE_BACKEND_BASE_URL || "http://127.0.0.1:8000"
	).replace(/\/$/, "");

	const [value, setValue] = useState("");
	const [isTyping, setIsTyping] = useState(false);
	const [chatHistory, setChatHistory] = useState<ChatTurn[]>([]);
	const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
	const [chatError, setChatError] = useState<string | null>(null);
	const [statusText, setStatusText] = useState<string>("");

	const fileInputRef = useRef<HTMLInputElement>(null);
	const textareaRef = useRef<HTMLTextAreaElement>(null);
	const scrollRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!scrollRef.current) return;
		scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
	}, [chatHistory, attachments]);

	const autoResize = () => {
		const textarea = textareaRef.current;
		if (!textarea) return;
		textarea.style.height = "44px";
		textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
	};

	const uploadOneFile = async (attachmentId: string, file: File) => {
		const formData = new FormData();
		formData.append("file", file);
		formData.append("source_id", file.name);

		const response = await fetch(`${apiBase}/api/upload-pdf`, {
			method: "POST",
			body: formData,
		});

		if (!response.ok) {
			throw new Error(await parseError(response));
		}

		const payload = (await response.json()) as {
			source_id?: string;
			ingested?: number;
		};
		setAttachments((prev) =>
			prev.map((item) =>
				item.id === attachmentId
					? {
							...item,
							status: "ready",
							sourceId: payload.source_id || file.name,
						}
					: item,
			),
		);
		setStatusText(`Ingested ${file.name} (${payload.ingested ?? 0} chunks)`);
	};

	const onFileSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
		const files = Array.from(event.target.files || []);
		if (files.length === 0) return;

		const newItems = files.map((file) => ({
			id: createId(),
			name: file.name,
			status: "uploading" as const,
		}));
		setAttachments((prev) => [...prev, ...newItems]);
		setChatError(null);

		for (let i = 0; i < files.length; i += 1) {
			const file = files[i];
			const item = newItems[i];
			try {
				await uploadOneFile(item.id, file);
			} catch (error) {
				const message = getErrorMessage(error);
				setAttachments((prev) =>
					prev.map((entry) =>
						entry.id === item.id
							? { ...entry, status: "failed", error: message }
							: entry,
					),
				);
				setChatError(`Failed to upload ${file.name}: ${message}`);
			}
		}

		event.target.value = "";
	};

	const removeAttachment = (id: string) => {
		setAttachments((prev) => prev.filter((item) => item.id !== id));
	};

	const handleSendMessage = async () => {
		const question = value.trim();
		if (!question) return;

		setIsTyping(true);
		setChatError(null);

		try {
			const response = await fetch(`${apiBase}/api/chat`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ question, top_k: 5 }),
			});

			if (!response.ok) {
				throw new Error(await parseError(response));
			}

			const payload = (await response.json()) as {
				answer?: string;
				sources?: string[];
			};
			setChatHistory((prev) => [
				...prev,
				{
					question,
					answer: payload.answer || "(No answer returned)",
					sources: Array.isArray(payload.sources) ? payload.sources : [],
				},
			]);
			setStatusText("");
			setValue("");
			if (textareaRef.current) textareaRef.current.style.height = "44px";
		} catch (error) {
			setChatError(getErrorMessage(error));
		} finally {
			setIsTyping(false);
		}
	};

	const handleKeyDown = async (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			await handleSendMessage();
		}
	};

	return (
		<div className="min-h-screen bg-[#f7f7f8] text-black">
			<input
				ref={fileInputRef}
				type="file"
				accept="application/pdf,.pdf"
				multiple
				className="hidden"
				onChange={onFileSelected}
			/>

			<div className="mx-auto flex h-screen w-full max-w-4xl flex-col">
				<header className="border-b border-black/10 px-4 py-3 text-sm font-medium">
					Ingest IQ
				</header>

				<main ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
					{chatHistory.length === 0 && (
						<div className="mx-auto mt-24 max-w-xl text-center">
							<h1 className="text-3xl font-semibold tracking-tight text-black">
								Ingest IQ
							</h1>
							<p className="mt-2 text-sm text-black/55">
								Ingest your PDFs and get fast, grounded answers from your
								knowledge base.
							</p>
							<div className="mt-4 flex items-center justify-center gap-4 text-black">
								<FileText className="h-5 w-5" />
								<Database className="h-5 w-5" />
								<Search className="h-5 w-5" />
								<MessageSquare className="h-5 w-5" />
							</div>
						</div>
					)}

					<div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
						{chatHistory.map((turn, idx) => (
							<div key={`${turn.question}-${idx}`} className="space-y-3">
								<div className="flex justify-end">
									<div className="max-w-[85%] rounded-2xl bg-[#303030] px-4 py-3 text-sm text-white">
										{turn.question}
									</div>
								</div>
								<div className="flex justify-start">
									<div className="max-w-[95%] rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-black/90">
										<p>{turn.answer}</p>
										{turn.sources.length > 0 && (
											<p className="mt-2 text-xs text-black/60">
												Sources: {turn.sources.join(", ")}
											</p>
										)}
									</div>
								</div>
							</div>
						))}

						{isTyping && (
							<div className="flex justify-start">
								<div className="inline-flex items-center gap-2 rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-black/70">
									<LoaderIcon className="h-4 w-4 animate-spin" /> Thinking...
								</div>
							</div>
						)}
					</div>
				</main>

				<div className="border-t border-black/10 bg-[#f7f7f8] px-4 py-4">
					<div className="mx-auto w-full max-w-3xl space-y-2">
						{attachments.length > 0 && (
							<div className="flex flex-wrap gap-2">
								{attachments.map((file) => (
									<div
										key={file.id}
										className="inline-flex items-center gap-2 rounded-lg border border-black/10 bg-white px-2.5 py-1.5 text-xs"
									>
										<span>{file.name}</span>
										<span className="uppercase text-black/50">
											{file.status}
										</span>
										<button
											onClick={() => removeAttachment(file.id)}
											className="text-black/40 hover:text-black"
										>
											<XIcon className="h-3.5 w-3.5" />
										</button>
									</div>
								))}
							</div>
						)}

						<div className="rounded-2xl border border-black/15 bg-white p-2 shadow-sm">
							<div className="flex items-end gap-2">
								<button
									type="button"
									onClick={() => fileInputRef.current?.click()}
									className="rounded-lg p-2 text-black/60 hover:bg-black/5 hover:text-black"
									aria-label="Upload PDF"
								>
									<Paperclip className="h-5 w-5" />
								</button>

								<textarea
									ref={textareaRef}
									value={value}
									onChange={(e) => {
										setValue(e.target.value);
										autoResize();
									}}
									onKeyDown={handleKeyDown}
									placeholder="Message RAG Assistant"
									rows={1}
									className="max-h-[180px] min-h-[44px] w-full resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-black/40"
								/>

								<button
									type="button"
									onClick={() => void handleSendMessage()}
									disabled={isTyping || !value.trim()}
									className={cn(
										"rounded-lg p-2 transition-colors",
										value.trim() && !isTyping
											? "bg-[#303030] text-white hover:bg-black"
											: "bg-black/10 text-black/40",
									)}
									aria-label="Send"
								>
									<SendIcon className="h-5 w-5" />
								</button>
							</div>
						</div>

						{statusText && (
							<p className="text-xs text-black/60">{statusText}</p>
						)}
						{chatError && <p className="text-sm text-red-600">{chatError}</p>}
					</div>
				</div>
			</div>
		</div>
	);
}
