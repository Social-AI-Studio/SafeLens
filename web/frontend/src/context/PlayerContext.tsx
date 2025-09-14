"use client";

import React, { createContext, useCallback, useContext, useMemo, useRef } from "react";

type TimeListener = (t: number) => void;

export interface PlayerContextValue {
    playerRef: React.MutableRefObject<any | null>;
    setPlayer: (player: any | null) => void;
    seekTo: (t: number) => void;
    subscribeTime: (fn: TimeListener) => () => void;
}

const noop = () => {};

const defaultValue: PlayerContextValue = {
    playerRef: { current: null },
    setPlayer: noop,
    seekTo: noop,
    subscribeTime: () => noop,
};

const PlayerContext = createContext<PlayerContextValue>(defaultValue);

export function PlayerProvider({ children }: { children: React.ReactNode }) {
    const playerRef = useRef<any | null>(null);
    const listenersRef = useRef<Set<TimeListener>>(new Set());
    const attachedPlayerRef = useRef<any | null>(null);
    const handlerRef = useRef<(() => void) | null>(null);
    const rafRef = useRef<number | null>(null);
    const rafLoopRef = useRef<number | null>(null);

    const fanOutTime = useCallback((t: number) => {
        // Coalesce multiple calls into next animation frame for smoother updates
        if (rafRef.current != null) {
            cancelAnimationFrame(rafRef.current);
        }
        rafRef.current = requestAnimationFrame(() => {
            listenersRef.current.forEach((fn) => {
                try {
                    fn(t);
                } catch {
                    // ignore listener errors
                }
            });
        });
    }, []);

    const stopRafLoop = useCallback(() => {
        if (rafLoopRef.current != null) {
            cancelAnimationFrame(rafLoopRef.current);
            rafLoopRef.current = null;
        }
    }, []);

    const startRafLoop = useCallback(
        (player: any) => {
            stopRafLoop();
            const loop = () => {
                try {
                    // Only fan-out if there are subscribers
                    if (
                        listenersRef.current.size > 0 &&
                        player &&
                        typeof player.currentTime === "function"
                    ) {
                        const t = player.currentTime();
                        listenersRef.current.forEach((fn) => {
                            try {
                                fn(t);
                            } catch {}
                        });
                    }
                } catch {
                    // ignore polling errors
                }
                rafLoopRef.current = requestAnimationFrame(loop);
            };
            rafLoopRef.current = requestAnimationFrame(loop);
        },
        [stopRafLoop],
    );

    const detachFromPlayer = useCallback(() => {
        const prev = attachedPlayerRef.current;
        if (prev && handlerRef.current) {
            try {
                prev.off("timeupdate", handlerRef.current);
                prev.off("seeked", handlerRef.current as any);
                prev.off("ratechange", handlerRef.current as any);
                prev.off("playing", handlerRef.current as any);
                prev.off("loadedmetadata", handlerRef.current as any);
            } catch {
                // ignore detach errors
            }
        }
        stopRafLoop();
        attachedPlayerRef.current = null;
        handlerRef.current = null;
    }, [stopRafLoop]);

    const attachToPlayer = useCallback(
        (player: any | null) => {
            detachFromPlayer();
            if (!player) return;

            const onTimeUpdate = () => {
                try {
                    const t =
                        typeof player.currentTime === "function"
                            ? player.currentTime()
                            : 0;
                    fanOutTime(t);
                } catch {
                    // ignore errors from player
                }
            };
            handlerRef.current = onTimeUpdate;
            try {
                player.on("timeupdate", onTimeUpdate);
                // Also respond immediately to important state changes with same handler for easy detach
                try {
                    player.on("seeked", onTimeUpdate);
                } catch {}
                try {
                    player.on("ratechange", onTimeUpdate);
                } catch {}
                try {
                    player.on("playing", onTimeUpdate);
                } catch {}
                try {
                    player.on("loadedmetadata", onTimeUpdate);
                } catch {}
                attachedPlayerRef.current = player;
                // Start high-frequency polling loop to reduce perceived latency
                startRafLoop(player);
            } catch {
                // ignore attach errors
            }
        },
        [detachFromPlayer, fanOutTime, startRafLoop],
    );

    const setPlayer = useCallback(
        (player: any | null) => {
            playerRef.current = player;
            attachToPlayer(player);
        },
        [attachToPlayer],
    );

    const seekTo = useCallback(
        (t: number) => {
            const p = playerRef.current;
            if (p && typeof p.currentTime === "function") {
                try {
                    p.currentTime(t);
                    // Immediately fan-out time for instant visual feedback
                    fanOutTime(t);
                } catch {
                    // ignore seek errors
                }
            }
        },
        [fanOutTime],
    );

    const subscribeTime = useCallback((fn: TimeListener) => {
        listenersRef.current.add(fn);
        return () => {
            listenersRef.current.delete(fn);
        };
    }, []);

    const value = useMemo<PlayerContextValue>(
        () => ({
            playerRef,
            setPlayer,
            seekTo,
            subscribeTime,
        }),
        [setPlayer, seekTo, subscribeTime],
    );

    return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

export function usePlayer(): PlayerContextValue {
    return useContext(PlayerContext);
}
