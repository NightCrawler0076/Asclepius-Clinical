import 'package:flutter/material.dart';
import 'mic_screen.dart';
import 'system_audio_screen.dart';
import 'file_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Whisper Transcriber'),
        centerTitle: true,
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Choose a transcription mode',
              style: TextStyle(fontSize: 16, color: Colors.grey),
            ),
            const SizedBox(height: 20),
            _ModeCard(
              icon: Icons.mic,
              title: 'Live Microphone',
              subtitle: 'Record yourself speaking and transcribe it',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const MicScreen()),
              ),
            ),
            const SizedBox(height: 14),
            _ModeCard(
              icon: Icons.speaker,
              title: 'System / Device Audio',
              subtitle: 'Desktop-app only — not available in a browser',
              disabled: true,
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const SystemAudioScreen()),
              ),
            ),
            const SizedBox(height: 14),
            _ModeCard(
              icon: Icons.folder_open,
              title: 'Prerecorded File',
              subtitle: 'Pick an existing audio file to transcribe',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const FileScreen()),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ModeCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool disabled;

  const _ModeCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.disabled = false,
  });

  @override
  Widget build(BuildContext context) {
    final iconColor = disabled ? Colors.grey.shade400 : Colors.deepPurple;
    final iconBg = disabled ? Colors.grey.shade200 : Colors.deepPurple.shade50;
    final titleColor = disabled ? Colors.grey.shade500 : Colors.black87;

    return Material(
      color: disabled ? Colors.grey.shade50 : Colors.white,
      borderRadius: BorderRadius.circular(14),
      elevation: disabled ? 0 : 1,
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: disabled ? null : onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.grey.shade300),
          ),
          child: Row(
            children: [
              CircleAvatar(
                radius: 24,
                backgroundColor: iconBg,
                child: Icon(icon, color: iconColor),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: titleColor)),
                    const SizedBox(height: 2),
                    Text(subtitle,
                        style: TextStyle(
                            fontSize: 13, color: Colors.grey.shade600)),
                  ],
                ),
              ),
              if (!disabled)
                const Icon(Icons.chevron_right, color: Colors.grey),
            ],
          ),
        ),
      ),
    );
  }
}
