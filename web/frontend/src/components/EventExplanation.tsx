"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { EVENT_PANEL_CSS } from "@/components/ui/constants";
import type { HarmfulContent } from "@/types/analysis";

interface EventExplanationProps {
    selectedEvent: HarmfulContent | null;
    // kept for compatibility; Event Details remains fixed height
    matchedMaxPx?: number | null;
}

export default function EventExplanation({ selectedEvent }: EventExplanationProps) {
    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    if (!selectedEvent) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Event Details</CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-base text-muted-foreground">
                        Click on an event from the timeline to view detailed information
                        about the harmful content detected.
                    </p>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card
            className="flex flex-col"
            style={{ height: EVENT_PANEL_CSS, maxHeight: "80vh" }}
        >
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    Event Details
                    <Badge variant="destructive" className="text-sm">
                        {Math.round(selectedEvent.confidence * 100)}%
                    </Badge>
                    {selectedEvent.confidence > 0.8 && (
                        <Badge variant="destructive" className="text-sm">
                            ⚠️ High Confidence
                        </Badge>
                    )}
                    {selectedEvent.confidence < 0.3 && (
                        <Badge
                            variant="outline"
                            className="text-sm border-yellow-400 text-yellow-700 bg-yellow-50"
                        >
                            ℹ️ Low Confidence
                        </Badge>
                    )}
                </CardTitle>
            </CardHeader>
            <CardContent className={"flex-1 min-h-0"}>
                <ScrollArea className={"w-full h-full"}>
                    <div className="space-y-4 pr-4">
                        {/* Basic Event Information */}
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <span className="text-base font-medium">
                                    Timestamp:
                                </span>
                                <span
                                    className="text-base font-mono bg-muted px-2 py-1 rounded"
                                    title={`${formatTime(selectedEvent.startTime)}–${formatTime(selectedEvent.endTime)} • ${Math.max(1, Math.round(selectedEvent.endTime - selectedEvent.startTime))}s`}
                                >
                                    {formatTime(selectedEvent.startTime)} –{" "}
                                    {formatTime(selectedEvent.endTime)}
                                </span>
                            </div>

                            <div className="flex items-center gap-2">
                                <span className="text-base font-medium">Duration:</span>
                                <span className="text-base">
                                    {Math.round(
                                        selectedEvent.endTime - selectedEvent.startTime,
                                    )}
                                    s
                                </span>
                            </div>

                            <div className="flex items-center gap-2">
                                <span className="text-base font-medium">
                                    Confidence:
                                </span>
                                <div className="flex items-center gap-2">
                                    <div className="w-20 bg-muted rounded-full h-2">
                                        <div
                                            className="bg-destructive h-2 rounded-full transition-all duration-300"
                                            style={{
                                                width: `${selectedEvent.confidence * 100}%`,
                                            }}
                                        />
                                    </div>
                                    <span className="text-base font-medium">
                                        {Math.round(selectedEvent.confidence * 100)}%
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Categories */}
                        <div>
                            <span className="text-base font-medium">Categories:</span>
                            <div className="mt-3 flex flex-wrap gap-1">
                                {(
                                    selectedEvent.categories ||
                                    selectedEvent.type.split(", ")
                                ).map((category, index) => (
                                    <Badge
                                        key={index}
                                        variant="outline"
                                        className="text-sm"
                                    >
                                        {typeof category === "string"
                                            ? category.trim()
                                            : category}
                                    </Badge>
                                ))}
                            </div>
                        </div>

                        {/* Detection Information */}
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <span className="text-base font-medium">
                                    Detection Source:
                                </span>
                                <Badge
                                    variant={
                                        selectedEvent.source === "vision"
                                            ? "default"
                                            : selectedEvent.source === "audio"
                                              ? "secondary"
                                              : selectedEvent.source === "ocr"
                                                ? "outline"
                                                : "destructive"
                                    }
                                    className="text-sm"
                                >
                                    {selectedEvent.source || "vision"}
                                </Badge>
                            </div>
                        </div>

                        {/* Description */}
                        {selectedEvent.description && (
                            <div>
                                <span className="text-base font-medium">
                                    Description:
                                </span>
                                <blockquote className="mt-3 pl-4 border-l-4 border-primary/30 bg-muted/30 py-2 pr-3 text-base text-foreground leading-relaxed italic">
                                    {selectedEvent.description}
                                </blockquote>
                            </div>
                        )}
                    </div>

                    {/*/!* Debug Info - Show raw data in development *!/*/}
                    {/*{selectedEvent.rawData && process.env.NODE_ENV === 'development' && (*/}
                    {/*    <details className="pt-2 border-t">*/}
                    {/*        <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">*/}
                    {/*            Debug: Raw Backend Data*/}
                    {/*        </summary>*/}
                    {/*        <pre className="text-xs bg-muted p-2 rounded mt-2 overflow-auto max-h-32">*/}
                    {/*            {JSON.stringify(selectedEvent.rawData, null, 2)}*/}
                    {/*        </pre>*/}
                    {/*    </details>*/}
                    {/*)}*/}
                </ScrollArea>
            </CardContent>
        </Card>
    );
}
