import { z } from "zod";

export const videoFileSchema = z.object({
    file: z
        .instanceof(File)
        .refine((file) => {
            const allowedTypes = [
                "video/mp4",
                "video/mov",
                "video/avi",
                "video/wmv",
                "video/webm",
                "video/mkv",
                "video/x-msvideo", // Alternative MIME type for AVI
                "video/quicktime", // Alternative MIME type for MOV
            ];
            return allowedTypes.includes(file.type);
        }, "Please upload a valid video file (MP4, MOV, AVI, WMV, WebM, MKV)")
        .refine((file) => {
            const maxSize = 500 * 1024 * 1024; // 500MB
            return file.size <= maxSize;
        }, "File size must be less than 500MB"),
});

export const videoUrlSchema = z.object({
    url: z
        .string()
        .url("Please enter a valid URL")
        .refine((url) => {
            // Check if URL ends with video extension or is from common video platforms
            const videoExtensions = /\.(mp4|mov|avi|wmv|webm|mkv)$/i;
            const videoPlatforms =
                /(youtube\.com|youtu\.be|vimeo\.com|dailymotion\.com)/i;

            return videoExtensions.test(url) || videoPlatforms.test(url);
        }, "URL must be a direct video link or from a supported platform"),
});

export type VideoFileInput = z.infer<typeof videoFileSchema>;
export type VideoUrlInput = z.infer<typeof videoUrlSchema>;
