// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'gen-fashion';

  @override
  String get navCloset => 'Closet';

  @override
  String get navCoordinate => 'Coordinate';

  @override
  String get navHistory => 'History';

  @override
  String get navShared => 'Shared';

  @override
  String get sharedClosetAbout => 'About shared closet';

  @override
  String get signOut => 'Sign out';

  @override
  String get language => 'Language';

  @override
  String get languageJapanese => 'Japanese';

  @override
  String get languageEnglish => 'English';

  @override
  String get loginEyebrow => 'Personal styling studio';

  @override
  String get loginSubtitle => 'Sign in to manage your closet.';

  @override
  String get signInLocal => 'Sign in locally';

  @override
  String get signInGoogle => 'Sign in with Google';

  @override
  String get signingIn => 'Signing in...';

  @override
  String signInFailed(Object error) {
    return 'Sign-in failed: $error';
  }

  @override
  String get closetTitle => 'Closet';

  @override
  String get addItem => 'Add item';

  @override
  String get uploading => 'Uploading...';

  @override
  String get uploadQueued => 'Upload queued; analyzing...';

  @override
  String get closetFull => 'Closet is full (20 items).';

  @override
  String uploadFailed(Object error) {
    return 'Upload failed: $error';
  }

  @override
  String get deleteItemQuestion => 'Delete item?';

  @override
  String get deleteItemBody => 'This removes the item from your closet.';

  @override
  String get cancel => 'Cancel';

  @override
  String get delete => 'Delete';

  @override
  String deleteFailed(Object error) {
    return 'Delete failed: $error';
  }

  @override
  String get editMetadata => 'Edit item metadata';

  @override
  String get category => 'Category';

  @override
  String get colorsComma => 'Colors (comma separated)';

  @override
  String get season => 'Season';

  @override
  String get tagsComma => 'Tags (comma separated)';

  @override
  String get gender => 'Gender';

  @override
  String get genderCommon => 'Common';

  @override
  String get genderFemale => 'Female';

  @override
  String get genderMale => 'Male';

  @override
  String get save => 'Save';

  @override
  String updateFailed(Object error) {
    return 'Update failed: $error';
  }

  @override
  String get emptyCloset => 'Add your first item to get started.';

  @override
  String get unknown => 'Unknown';

  @override
  String get analyzing => 'Analyzing...';

  @override
  String get analysisFailed => 'Analysis failed';

  @override
  String get statusProcessing => 'PROCESSING';

  @override
  String get statusReady => 'READY';

  @override
  String get statusError => 'ERROR';

  @override
  String get statusUnknown => 'UNKNOWN';

  @override
  String get deleteTooltip => 'Delete';

  @override
  String get editMetadataTooltip => 'Edit metadata';

  @override
  String get coordinationTitle => 'Coordination';

  @override
  String get modeStandard => 'Closet Styling';

  @override
  String get modeAssisted => 'Style & Shop';

  @override
  String get modeStandardHint =>
      'Creates a full outfit using only your closet items.';

  @override
  String get modeAssistedHint =>
      'Pick up to 3 of your own clothes; AI styles a full outfit and suggests items you can buy on Rakuten.';

  @override
  String get analyzingItem => 'Analyzing...';

  @override
  String get anchorItemsLabel => 'Your clothes (up to 3)';

  @override
  String get anchorLimitReached => 'You can select up to 3 items.';

  @override
  String get noReadyAnchorItems =>
      'No ready closet items yet. Upload one to begin.';

  @override
  String get sourceRakuten => 'Rakuten';

  @override
  String get addToCloset => 'Add to closet';

  @override
  String get savedAsInteresting => 'Saved as Interesting';

  @override
  String importFailed(Object error) {
    return 'Save failed: $error';
  }

  @override
  String get openProductPage => 'Open product page';

  @override
  String get saveInterestingDialogTitle => 'Save Rakuten items to your closet?';

  @override
  String get saveInterestingDialogBody =>
      'These Rakuten items were part of this outfit. Save the ones you like as \"Interesting\" so you can find them again.';

  @override
  String get saveInterestingSkip => 'Skip';

  @override
  String get saveInterestingConfirm => 'Save selected';

  @override
  String get ownership => 'Ownership';

  @override
  String get ownershipOwned => 'Owned';

  @override
  String get ownershipInteresting => 'Interesting';

  @override
  String get sourceShared => 'Shared';

  @override
  String get sourceMine => 'Mine';

  @override
  String get sharedCloset => 'Shared closet';

  @override
  String get occasion => 'Occasion';

  @override
  String get style => 'Style';

  @override
  String get colors => 'Colors';

  @override
  String selectedGenerationLanguage(Object language) {
    return 'Generation language: $language';
  }

  @override
  String get running => 'Running';

  @override
  String get start => 'Start';

  @override
  String get agentTrace => 'Agent trace';

  @override
  String errorWithMessage(Object error) {
    return 'Error: $error';
  }

  @override
  String get noSessionEvents => 'No session events yet.';

  @override
  String get chooseItems => 'Choose items';

  @override
  String get generateSelected => 'Generate selected';

  @override
  String get recommended => 'Recommended';

  @override
  String get item => 'Item';

  @override
  String get result => 'Result';

  @override
  String get coordinatePlaceholder => 'Coordinate image will appear here.';

  @override
  String traceSearchedCloset(Object agentName, Object count) {
    return '$agentName searched closet - $count candidates';
  }

  @override
  String traceSearchingCloset(Object agentName) {
    return '$agentName is searching the closet';
  }

  @override
  String traceGeneratedCoordinate(Object agentName) {
    return '$agentName generated the coordinate';
  }

  @override
  String traceGeneratingCoordinate(Object agentName) {
    return '$agentName is generating the coordinate';
  }

  @override
  String get tracePreview => 'Preview';

  @override
  String get traceRaw => 'Raw';

  @override
  String get traceDescription => 'Description';

  @override
  String get traceStyleDirection => 'Style';

  @override
  String get traceWearer => 'Wearer';

  @override
  String get traceItemCount => 'Items';

  @override
  String get traceModelUsed => 'Model';

  @override
  String get traceGenerationPrompt => 'Prompt';

  @override
  String get traceTags => 'Tags';

  @override
  String get traceTargetAgent => 'Agent';

  @override
  String traceItemsFound(int count) {
    return '$count items found';
  }

  @override
  String historyLoadFailed(Object error) {
    return 'Failed to load history: $error';
  }

  @override
  String get historyEmpty => 'No completed coordinates yet.';

  @override
  String get dateUnavailable => 'Date unavailable';

  @override
  String get myCloset => 'My Closet';

  @override
  String sharedGalleryError(Object error) {
    return 'Error: $error';
  }

  @override
  String get sharedAttribution =>
      'Shared closet images use the Clothing Dataset (CC BY-SA 4.0)';

  @override
  String get sharedAboutBody =>
      'Shared closet lets you try coordination without uploading clothes.';

  @override
  String get sharedAboutDataset =>
      'Image material: Clothing Dataset (CC BY-SA 4.0)';

  @override
  String get sharedAboutAuthor => 'Author: Alexey Grigorev';

  @override
  String get viewDataset => 'View dataset on Kaggle';

  @override
  String get close => 'Close';
}
