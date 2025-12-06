"use client";

import React, { createContext, useCallback, useContext, useMemo, useRef } from "react";
import type { MediaPlayerInstance } from "@vidstack/react";

type TimeListener = (t: number) => void;
type DurationListener = (d: number) => void;

export interface PlayerContextValue {
    playerRef: React.MutableRefObject<MediaPlayerInstance | null>;
    setPlayer: (player: MediaPlayerInstance | null) => void;
    seekTo: (t: number) => void;
    // For components that need to subscribe to time updates (legacy support)
    subscribeTime: (fn: TimeListener) => () => void;
    subscribeDuration: (fn: DurationListener) => () => void;
    // Direct time/duration fan-out for the player to call
    fanOutTime: (t: number) => void;
    fanOutDuration: (d: number) => void;
}

const noop = () => {};

const defaultValue: PlayerContextValue = {
    playerRef: { current: null },
    setPlayer: noop,
    seekTo: noop,
    subscribeTime: () => noop,
    subscribeDuration: () => noop,
    fanOutTime: noop,
    fanOutDuration: noop,
};

const PlayerContext = createContext<PlayerContextValue>(defaultValue);

export function PlayerProvider({ children }: { children: React.ReactNode }) {
    const playerRef = useRef<MediaPlayerInstance | null>(null);
    const listenersRef = useRef<Set<TimeListener>>(new Set());
    const durationListenersRef = useRef<Set<DurationListener>>(new Set());
    const lastDurationRef = useRef<number>(0);
    const rafRef = useRef<number | null>(null);

    const fanOutTime = useCallback((t: number) => {
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

    const fanOutDuration = useCallback((d: number) => {
        if (d > 0 && d !== lastDurationRef.current) {
            lastDurationRef.current = d;
            durationListenersRef.current.forEach((fn) => {
                try {
                    fn(d);
                } catch {
                    // ignore listener errors
                }
            });
        }
    }, []);

    const setPlayer = useCallback((player: MediaPlayerInstance | null) => {
        playerRef.current = player;
    }, []);

    const seekTo = useCallback((t: number) => {
        const p = playerRef.current;
        if (p) {
            try {
                p.currentTime = t;
                fanOutTime(t);
            } catch {
                // ignore seek errors
            }
        }
    }, [fanOutTime]);

    const subscribeTime = useCallback((fn: TimeListener) => {
        listenersRef.current.add(fn);
        return () => {
            listenersRef.current.delete(fn);
        };
    }, []);

    const subscribeDuration = useCallback((fn: DurationListener) => {
        durationListenersRef.current.add(fn);
        if (lastDurationRef.current > 0) {
            fn(lastDurationRef.current);
        }
        return () => {
            durationListenersRef.current.delete(fn);
        };
    }, []);

    const value = useMemo<PlayerContextValue>(
        () => ({
            playerRef,
            setPlayer,
            seekTo,
            subscribeTime,
            subscribeDuration,
            fanOutTime,
            fanOutDuration,
        }),
        [setPlayer, seekTo, subscribeTime, subscribeDuration, fanOutTime, fanOutDuration],
    );

    return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

export function usePlayer(): PlayerContextValue {
    return useContext(PlayerContext);
}
