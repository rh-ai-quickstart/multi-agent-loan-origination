// This project was developed with assistance from AI tools.

import { useState, useRef, useCallback } from 'react';
import {
    Root as DialogRoot,
    Portal as DialogPortal,
    Overlay as DialogOverlay,
    Content as DialogContent,
    Title as DialogTitle,
    Close as DialogClose,
} from '@radix-ui/react-dialog';
import { Camera, X, RefreshCw, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CameraCaptureProps {
    onCapture: (file: File) => void;
    disabled?: boolean;
}

type CameraState = 'idle' | 'streaming' | 'captured';

function canUseGetUserMedia(): boolean {
    return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
}

function isMobileDevice(): boolean {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(pointer: coarse)').matches;
}

export function CameraCapture({ onCapture, disabled }: CameraCaptureProps) {
    const [open, setOpen] = useState(false);
    const [state, setState] = useState<CameraState>('idle');
    const [error, setError] = useState<string | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const nativeInputRef = useRef<HTMLInputElement>(null);

    const stopStream = useCallback(() => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
        }
    }, []);

    const startStream = useCallback(async () => {
        setError(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' },
            });
            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
            setState('streaming');
        } catch (err) {
            const msg =
                err instanceof DOMException && (err.name === 'NotAllowedError' || err.name === 'NotFoundError')
                    ? 'Camera not available. Please check your permissions.'
                    : 'Could not access camera.';
            setError(msg);
        }
    }, []);

    const handleCapture = useCallback(() => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (!video || !canvas) return;

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.drawImage(video, 0, 0);
        canvas.toBlob(
            (blob) => {
                if (!blob) return;
                setCapturedBlob(blob);
                setPreviewUrl(URL.createObjectURL(blob));
                setState('captured');
                stopStream();
            },
            'image/jpeg',
            0.92,
        );
    }, [stopStream]);

    const handleRetake = useCallback(() => {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setPreviewUrl(null);
        setCapturedBlob(null);
        startStream();
    }, [previewUrl, startStream]);

    const handleUsePhoto = useCallback(() => {
        if (!capturedBlob) return;
        const file = new File([capturedBlob], `document-capture-${Date.now()}.jpg`, {
            type: 'image/jpeg',
        });
        onCapture(file);
        setOpen(false);
    }, [capturedBlob, onCapture]);

    const handleOpenChange = useCallback(
        (nextOpen: boolean) => {
            setOpen(nextOpen);
            if (nextOpen) {
                setState('idle');
                setError(null);
                setPreviewUrl(null);
                setCapturedBlob(null);
                // Use setTimeout(0) to start stream after dialog renders
                setTimeout(() => {
                    startStream();
                }, 0);
            } else {
                stopStream();
                if (previewUrl) URL.revokeObjectURL(previewUrl);
                setState('idle');
                setPreviewUrl(null);
                setCapturedBlob(null);
            }
        },
        [startStream, stopStream, previewUrl],
    );

    const handleNativeCapture = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const file = e.target.files?.[0];
            if (file) onCapture(file);
            if (nativeInputRef.current) nativeInputRef.current.value = '';
        },
        [onCapture],
    );

    const buttonClass = cn(
        'inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-foreground dark:border-slate-700 dark:hover:border-slate-600 dark:hover:bg-slate-800',
        disabled && 'pointer-events-none opacity-50',
    );

    // Only show camera capture on mobile/tablet devices
    if (!isMobileDevice()) return null;

    // No getUserMedia (mobile over HTTP, older browsers) -- use native file input
    // with capture="environment" which opens the OS camera directly
    if (!canUseGetUserMedia()) {
        return (
            <>
                <button
                    type="button"
                    disabled={disabled}
                    onClick={() => nativeInputRef.current?.click()}
                    className={buttonClass}
                >
                    <Camera className="h-4 w-4" />
                    Take a Photo
                </button>
                <input
                    ref={nativeInputRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={handleNativeCapture}
                />
            </>
        );
    }

    // getUserMedia available -- use the viewfinder dialog
    return (
        <DialogRoot open={open} onOpenChange={handleOpenChange}>
            <button
                type="button"
                disabled={disabled}
                onClick={() => handleOpenChange(true)}
                className={buttonClass}
            >
                <Camera className="h-4 w-4" />
                Take a Photo
            </button>
            <DialogPortal>
                <DialogOverlay className="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
                <DialogContent
                    className="fixed inset-0 z-50 flex flex-col bg-black sm:inset-4 sm:rounded-xl"
                    aria-describedby={undefined}
                >
                    <div className="flex items-center justify-between px-4 py-3">
                        <DialogTitle className="text-sm font-medium text-white">
                            Capture Document
                        </DialogTitle>
                        <DialogClose asChild>
                            <button
                                className="flex h-8 w-8 items-center justify-center rounded-full text-white/70 transition-colors hover:bg-white/10 hover:text-white"
                                aria-label="Close"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </DialogClose>
                    </div>

                    <div className="relative flex flex-1 items-center justify-center overflow-hidden">
                        {error ? (
                            <p className="px-8 text-center text-sm text-white/70">{error}</p>
                        ) : state === 'captured' && previewUrl ? (
                            <img
                                src={previewUrl}
                                alt="Captured document"
                                className="max-h-full max-w-full object-contain"
                            />
                        ) : (
                            <>
                                <video
                                    ref={videoRef}
                                    autoPlay
                                    playsInline
                                    muted
                                    className="absolute inset-0 h-full w-full object-cover"
                                />
                                {state === 'streaming' && (
                                    <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                                        <div className="aspect-[8.5/11] h-[70%] rounded-lg border-2 border-dashed border-white/50" />
                                        <p className="mt-2 text-xs text-white/50">
                                            Align document within the frame
                                        </p>
                                    </div>
                                )}
                            </>
                        )}
                    </div>

                    <div className="flex items-center justify-center gap-6 px-4 py-6">
                        {state === 'streaming' && (
                            <button
                                onClick={handleCapture}
                                className="flex h-16 w-16 items-center justify-center rounded-full border-4 border-white bg-white/20 transition-colors hover:bg-white/40"
                                aria-label="Take photo"
                            >
                                <div className="h-12 w-12 rounded-full bg-white" />
                            </button>
                        )}
                        {state === 'captured' && (
                            <>
                                <button
                                    onClick={handleRetake}
                                    className="flex items-center gap-2 rounded-lg bg-white/10 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-white/20"
                                >
                                    <RefreshCw className="h-4 w-4" />
                                    Retake
                                </button>
                                <button
                                    onClick={handleUsePhoto}
                                    className="flex items-center gap-2 rounded-lg bg-white px-4 py-2.5 text-sm font-medium text-black transition-colors hover:bg-white/90"
                                >
                                    <Check className="h-4 w-4" />
                                    Use Photo
                                </button>
                            </>
                        )}
                    </div>

                    <canvas ref={canvasRef} className="hidden" />
                </DialogContent>
            </DialogPortal>
        </DialogRoot>
    );
}
