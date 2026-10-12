from pathlib import Path
p = Path("LogicAnalyzer.c")
s = p.read_text()
# Output-only change: do not modify capture calls, pin mapping, trigger, DMA, PIO, or command parser.
start = s.index("                //Send the data to the host\n", s.index("int main()"))
end = s.index("                //Done!\n", start)
replacement = r'''                // CoolTerm CSV output of the completed capture.
                // Original channel ordering is preserved: channel 0 = bit 0, etc.
                // No changes to capture initiation, trigger, or sampling.
                (void)timestamps;
                (void)stampsLength;
                uint32_t sampleBytes = mode == MODE_8_CHANNEL ? 1u :
                                       mode == MODE_16_CHANNEL ? 2u : 4u;
                uint32_t bufferSamples = CAPTURE_BUFFER_SIZE / sampleBytes;
                printf("# CAPTURE,SAMPLES,%lu,CHANNEL_BYTES,%lu\\n",
                       (unsigned long)length, (unsigned long)sampleBytes);
                printf("sample,value_hex\\n");
                for (uint32_t i = 0; i < length; i++)
                {
                    uint32_t index = ((first + i) % bufferSamples) * sampleBytes;
                    uint32_t value = 0;
                    for (uint32_t j = 0; j < sampleBytes; j++)
                        value |= ((uint32_t)buffer[index + j]) << (8u * j);
                    printf("%lu,0x%08lX\\n", (unsigned long)i, (unsigned long)value);
                }
                printf("# END_CAPTURE\\n");
                fflush(stdout);
'''
# r-string above uses escaped backslashes for the Python generator;
# normalize to C newline escapes, never raw newline inside a C literal.
replacement = replacement.replace('\\\\n', '\\n')
s = s[:start] + replacement + s[end:]
p.write_text(s)
print("Patched ONLY original host-data output block")
