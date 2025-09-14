"use client";

import { useState } from "react";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

interface ModelSelectorProps {
    value?: string;
    onModelChange?: (model: string) => void;
}

const models = [
    { value: "meta-llama/llama-3-8b-instruct", label: "Llama 3 8B" },
    { value: "SafeLens/llama-3-8b", label: "Llama 3 8B (FT)" },
    { value: "google/gemini-2.0-flash-001", label: "Gemini Flash 2.0" },
];

export default function ModelSelector({ value, onModelChange }: ModelSelectorProps) {
    const handleModelChange = (model: string) => {
        onModelChange?.(model);
    };

    return (
        <div className="flex items-center gap-3">
            <Label
                htmlFor="model-selector"
                className="text-sm font-medium whitespace-nowrap"
            >
                Analysis Model:
            </Label>
            <Select
                value={value || "SafeLens/llama-3-8b"}
                onValueChange={handleModelChange}
            >
                <SelectTrigger id="model-selector" className="w-[200px]">
                    <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                    {models.map((model) => (
                        <SelectItem key={model.value} value={model.value}>
                            {model.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}
