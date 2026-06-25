import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

const _kAttributionText =
    '共有クローゼットの画像は Clothing Dataset (CC BY-SA 4.0) を使用しています';
const _kKaggleUrl =
    'https://www.kaggle.com/datasets/agrigorev/clothing-dataset-full';

/// Compact footer placed at the bottom of screens that surface shared-closet items.
class AttributionFooter extends StatelessWidget {
  const AttributionFooter({super.key});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => showSharedClosetAboutDialog(context),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.info_outline,
              size: 14,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                _kAttributionText,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Shows a dialog explaining the shared closet and its CC BY-SA 4.0 licence.
void showSharedClosetAboutDialog(BuildContext context) {
  showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('共有クローゼットについて'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '共有クローゼットでは、アップロードなしにコーディネートを試すことができます。',
          ),
          const SizedBox(height: 12),
          const Text(
            '画像素材: Clothing Dataset (CC BY-SA 4.0)',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          const Text('著作者: Alexey Grigorev'),
          const SizedBox(height: 8),
          TextButton.icon(
            onPressed: () => _launchUrl(_kKaggleUrl),
            icon: const Icon(Icons.open_in_new, size: 16),
            label: const Text('Kaggle でデータセットを見る'),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(),
          child: const Text('閉じる'),
        ),
      ],
    ),
  );
}

Future<void> _launchUrl(String url) async {
  final uri = Uri.parse(url);
  if (await canLaunchUrl(uri)) {
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}
