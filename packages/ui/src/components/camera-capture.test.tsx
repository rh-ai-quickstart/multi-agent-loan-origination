// This project was developed with assistance from AI tools.

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CameraCapture } from './camera-capture';

describe('CameraCapture', () => {
    beforeEach(() => {
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia: vi.fn() },
            writable: true,
            configurable: true,
        });
    });

    it('should render camera button when getUserMedia is available', () => {
        render(<CameraCapture onCapture={vi.fn()} />);
        expect(screen.getByTitle('Take a photo')).toBeInTheDocument();
    });

    it('should not render when getUserMedia is unavailable', () => {
        Object.defineProperty(navigator, 'mediaDevices', {
            value: undefined,
            writable: true,
            configurable: true,
        });

        const { container } = render(<CameraCapture onCapture={vi.fn()} />);
        expect(container.innerHTML).toBe('');
    });

    it('should render as disabled when disabled prop is true', () => {
        render(<CameraCapture onCapture={vi.fn()} disabled />);
        expect(screen.getByTitle('Take a photo')).toBeDisabled();
    });

    it('should open dialog and request camera on click', async () => {
        const mockStream = {
            getTracks: () => [{ stop: vi.fn() }],
        } as unknown as MediaStream;

        const getUserMedia = vi.fn().mockResolvedValue(mockStream);
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia },
            writable: true,
            configurable: true,
        });

        render(<CameraCapture onCapture={vi.fn()} />);
        fireEvent.click(screen.getByTitle('Take a photo'));

        expect(screen.getByText('Capture Document')).toBeInTheDocument();
        await waitFor(() => {
            expect(getUserMedia).toHaveBeenCalledWith({
                video: { facingMode: 'environment' },
            });
        });
    });

    it('should show error message when camera permission is denied', async () => {
        const getUserMedia = vi.fn().mockRejectedValue(
            new DOMException('Permission denied', 'NotAllowedError'),
        );
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia },
            writable: true,
            configurable: true,
        });

        render(<CameraCapture onCapture={vi.fn()} />);
        fireEvent.click(screen.getByTitle('Take a photo'));

        expect(
            await screen.findByText('Camera not available. Please check your permissions.'),
        ).toBeInTheDocument();
    });

    it('should show generic error when camera fails for unknown reason', async () => {
        const getUserMedia = vi.fn().mockRejectedValue(new Error('Unknown error'));
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia },
            writable: true,
            configurable: true,
        });

        render(<CameraCapture onCapture={vi.fn()} />);
        fireEvent.click(screen.getByTitle('Take a photo'));

        expect(
            await screen.findByText('Could not access camera.'),
        ).toBeInTheDocument();
    });

    it('should stop stream tracks when dialog is closed', async () => {
        const stopTrack = vi.fn();
        const mockStream = {
            getTracks: () => [{ stop: stopTrack }],
        } as unknown as MediaStream;

        const getUserMedia = vi.fn().mockResolvedValue(mockStream);
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia },
            writable: true,
            configurable: true,
        });

        render(<CameraCapture onCapture={vi.fn()} />);
        fireEvent.click(screen.getByTitle('Take a photo'));

        await waitFor(() => expect(getUserMedia).toHaveBeenCalled());

        fireEvent.click(screen.getByLabelText('Close'));

        await waitFor(() => expect(stopTrack).toHaveBeenCalled());
    });

    it('should not propagate click to parent elements', () => {
        const parentClick = vi.fn();

        render(
            <div onClick={parentClick} role="presentation">
                <CameraCapture onCapture={vi.fn()} />
            </div>,
        );

        fireEvent.click(screen.getByTitle('Take a photo'));
        expect(parentClick).not.toHaveBeenCalled();
    });
});
