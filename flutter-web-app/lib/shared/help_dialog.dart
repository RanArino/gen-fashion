import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../l10n/app_localizations.dart';

const _kKaggleUrl =
    'https://www.kaggle.com/datasets/agrigorev/clothing-dataset-full';

const helpSectionCloset = 'closet';
const helpSectionCoordinate = 'coordinate';
const helpSectionHistory = 'history';
const helpSectionShared = 'shared';

/// Shows one app-wide help dialog with a collapsible per-page section for
/// each tab. [initialSection] (one of the `helpSection*` constants) is
/// expanded by default; the rest start collapsed.
void showAppHelpDialog(BuildContext context, {required String initialSection}) {
  final l10n = AppLocalizations.of(context)!;
  showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(l10n.appHelpTitle),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                initiallyExpanded: initialSection == helpSectionCloset,
                title: Text(l10n.navCloset),
                children: [
                  _SectionBody(children: [
                    Text(l10n.closetHelpPurpose),
                    const SizedBox(height: 8),
                    Text(l10n.closetHelpUpload),
                    const SizedBox(height: 8),
                    Text(l10n.closetHelpFilters),
                  ]),
                ],
              ),
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                initiallyExpanded: initialSection == helpSectionCoordinate,
                title: Text(l10n.navCoordinate),
                children: [
                  _SectionBody(children: [
                    Text(l10n.helpCoordinateIntro),
                    const SizedBox(height: 8),
                    Text(l10n.modeStandardHint),
                    const SizedBox(height: 4),
                    Text(l10n.modeAssistedHint),
                    const SizedBox(height: 8),
                    Text(l10n.sourceSharedHint),
                    const SizedBox(height: 4),
                    Text(l10n.sourceMineHint),
                  ]),
                ],
              ),
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                initiallyExpanded: initialSection == helpSectionHistory,
                title: Text(l10n.navHistory),
                children: [
                  _SectionBody(children: [
                    Text(l10n.helpHistoryBody),
                  ]),
                ],
              ),
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                initiallyExpanded: initialSection == helpSectionShared,
                title: Text(l10n.navShared),
                children: [
                  _SectionBody(children: [
                    Text(l10n.sharedAboutBody),
                    const SizedBox(height: 12),
                    Text(
                      l10n.sharedAboutDataset,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    Text(l10n.sharedAboutAuthor),
                    const SizedBox(height: 8),
                    TextButton.icon(
                      onPressed: () => _launchUrl(_kKaggleUrl),
                      icon: const Icon(Icons.open_in_new, size: 16),
                      label: Text(l10n.viewDataset),
                    ),
                  ]),
                ],
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(),
          child: Text(l10n.close),
        ),
      ],
    ),
  );
}

class _SectionBody extends StatelessWidget {
  const _SectionBody({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }
}

Future<void> _launchUrl(String url) async {
  final uri = Uri.parse(url);
  if (await canLaunchUrl(uri)) {
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}
