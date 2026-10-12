from pathlib import Path
p=Path("LogicAnalyzer.c")
s=p.read_text()
marker="//Buffer used to store received data"
assert s.count(marker)==1
helpers=r'''
// CoolTerm transport only. Capture engine (PIO/DMA/trigger) is unmodified.
#define CT_RATE 100000000u
#define CT_COUNT 8192u
static const uint8_t ct_pins[2] = {0,1}; // GusmanB channel indexes: GP2, GP3
static uint32_t ct_batch=0;
static bool ct_start(void) {
    // Original V6 API, positive trigger on GP2.
    return StartCaptureSimple(CT_RATE,0,CT_COUNT,0,0,ct_pins,2,0,false,MODE_8_CHANNEL);
}
static void ct_output(const uint8_t *buffer,uint32_t length,uint32_t first) {
    printf("# BATCH,%lu,SAMPLES,%lu,RATE_HZ,%u\n",
           (unsigned long)++ct_batch,(unsigned long)length,CT_RATE);
    printf("sample,SCLK,SDATA\n");
    for(uint32_t i=0;i<length;++i) {
        uint8_t v=buffer[(first+i)%CAPTURE_BUFFER_SIZE];
        printf("%lu,%u,%u\n",(unsigned long)i,(unsigned)(v&1u),(unsigned)((v>>1)&1u));
    }
    printf("# END_BATCH\n");
    fflush(stdout);
}
'''
s=s.replace(marker,helpers+marker)
start=s.index("                //Send the data to the host\n",s.index("int main()"))
end=s.index("                //Done!\n",start)
s=s[:start]+'''                (void)timestamps;
                (void)stampsLength;
                if(mode==MODE_8_CHANNEL) ct_output(buffer,length,first);
                else printf("# ERROR,UNEXPECTED_MODE\\n");
'''+s[end:]
needle="    while(1)\n    {\n        //Are we capturing?"
assert s.count(needle)==1
s=s.replace(needle,'''    printf("# COOLTERM,READY,GP2=SCLK,GP3=SDATA,RATE=100000000\\n");
    capturing=ct_start();
    printf(capturing ? "# CAPTURE,ARMED,TRIGGER=GP2_RISING\\n" : "# ERROR,CAPTURE_START_FAILED\\n");
    while(1)
    {
        //Are we capturing?''')
needle="                //Done!\n                capturing = false;"
assert s.count(needle)==1
s=s.replace(needle,'''                //Done!
                capturing=ct_start();
                printf(capturing ? "# CAPTURE,REARMED\\n" : "# ERROR,CAPTURE_REARM_FAILED\\n");''')
s=s.replace("            processInput(); //Read incomming data",'''            // Retry failed arm; preserve V6 capture logic.
            sleep_ms(100);
            capturing=ct_start();
            if(!capturing) printf("# ERROR,CAPTURE_START_FAILED\\n");''')
p.write_text(s)
print("patched")
