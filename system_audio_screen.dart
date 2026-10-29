import 'package:flutter/material.dart';

// This mode mirrors test3_ondevice.py (capturing whatever is playing out
// of the device's speakers). It's disabled in the web build: browsers
// sandbox pages away from OS-level loopback audio access entirely — there
// is no web API for "record what this machine is playing." Reinstating
// this screen only makes sense in a future Windows-desktop build, where
// a Python backend running on that same PC can do the actual capture
// (see test3_ondevice.py) and this screen would just call start/stop
// endpoints on it, same shape as the mic and file screens.

class SystemAudioScreen extends StatelessWidget {
  const SystemAudioScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('System / Device Audio')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.speaker_notes_off,
                  size: 48, color: Colors.grey.shade400),
              const SizedBox(height: 16),
              const Text(
                'Not available in the browser',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              Text(
                'Capturing a device\'s own audio output requires OS-level '
                'access that browsers don\'t allow. This mode will work in '
                'a future Windows desktop build.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey.shade600, height: 1.4),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
