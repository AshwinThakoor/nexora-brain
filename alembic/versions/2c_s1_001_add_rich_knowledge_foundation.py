"""add rich knowledge foundation

Revision ID: 2c_s1_001
Revises: 2b_s2_001
Create Date: 2026-07-26 19:45:19.715541

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = '2c_s1_001'
down_revision: Union[str, Sequence[str], None] = '2b_s2_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the Pack 2C rich-knowledge and governance foundation."""
    op.create_table('knowledge_reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entity_type', sa.String(length=100), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.Column('reviewer', sa.String(length=255), nullable=True),
    sa.Column('review_status', sa.String(length=50), nullable=False),
    sa.Column('decision', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_review_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('knowledge_reviews', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_knowledge_reviews_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_knowledge_reviews_entity_type'), ['entity_type'], unique=False)

    op.create_table('knowledge_revisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entity_type', sa.String(length=100), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('change_type', sa.String(length=100), nullable=False),
    sa.Column('change_summary', sa.Text(), nullable=False),
    sa.Column('snapshot_json', sa.JSON(), nullable=False),
    sa.Column('created_by', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entity_type', 'entity_id', 'version_number', name='uq_knowledge_revision_entity_version')
    )
    with op.batch_alter_table('knowledge_revisions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_knowledge_revisions_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_knowledge_revisions_entity_type'), ['entity_type'], unique=False)

    op.create_table('source_assessments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('authority_score', sa.Float(), nullable=True),
    sa.Column('accuracy_score', sa.Float(), nullable=True),
    sa.Column('recency_score', sa.Float(), nullable=True),
    sa.Column('transparency_score', sa.Float(), nullable=True),
    sa.Column('relevance_score', sa.Float(), nullable=True),
    sa.Column('overall_score', sa.Float(), nullable=True),
    sa.Column('assessment_method', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('accuracy_score IS NULL OR (accuracy_score >= 0.0 AND accuracy_score <= 1.0)', name='ck_source_assessments_accuracy_score_range'),
    sa.CheckConstraint('authority_score IS NULL OR (authority_score >= 0.0 AND authority_score <= 1.0)', name='ck_source_assessments_authority_score_range'),
    sa.CheckConstraint('overall_score IS NULL OR (overall_score >= 0.0 AND overall_score <= 1.0)', name='ck_source_assessments_overall_score_range'),
    sa.CheckConstraint('recency_score IS NULL OR (recency_score >= 0.0 AND recency_score <= 1.0)', name='ck_source_assessments_recency_score_range'),
    sa.CheckConstraint('relevance_score IS NULL OR (relevance_score >= 0.0 AND relevance_score <= 1.0)', name='ck_source_assessments_relevance_score_range'),
    sa.CheckConstraint('transparency_score IS NULL OR (transparency_score >= 0.0 AND transparency_score <= 1.0)', name='ck_source_assessments_transparency_score_range'),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('source_assessments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_source_assessments_source_id'), ['source_id'], unique=False)

    op.create_table('asset_classes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('market_structure', sa.Text(), nullable=False),
    sa.Column('typical_participants', sa.Text(), nullable=False),
    sa.Column('risk_profile', sa.Text(), nullable=False),
    sa.Column('trading_hours_notes', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('concept_id')
    )
    op.create_table('concept_aliases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('alias', sa.String(length=500), nullable=False),
    sa.Column('normalized_alias', sa.String(length=500), nullable=False),
    sa.Column('alias_type', sa.String(length=100), nullable=True),
    sa.Column('language', sa.String(length=20), nullable=False),
    sa.Column('is_preferred', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('concept_id', 'normalized_alias', 'language', name='uq_concept_alias_normalized_language')
    )
    with op.batch_alter_table('concept_aliases', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_concept_aliases_concept_id'), ['concept_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_concept_aliases_normalized_alias'), ['normalized_alias'], unique=False)

    op.create_table('economic_event_types',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('country_or_region', sa.String(length=255), nullable=True),
    sa.Column('frequency', sa.String(length=100), nullable=True),
    sa.Column('release_authority', sa.String(length=255), nullable=True),
    sa.Column('affected_assets_json', sa.JSON(), nullable=True),
    sa.Column('interpretation_rules', sa.Text(), nullable=True),
    sa.Column('typical_volatility_effect', sa.Text(), nullable=True),
    sa.Column('pre_event_risk_policy', sa.Text(), nullable=True),
    sa.Column('post_event_risk_policy', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('concept_id')
    )
    op.create_table('formulas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('expression', sa.Text(), nullable=False),
    sa.Column('latex_expression', sa.Text(), nullable=True),
    sa.Column('variables_json', sa.JSON(), nullable=True),
    sa.Column('assumptions', sa.Text(), nullable=True),
    sa.Column('interpretation', sa.Text(), nullable=False),
    sa.Column('worked_example', sa.Text(), nullable=True),
    sa.Column('limitations', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('concept_id', 'name', name='uq_formula_concept_name')
    )
    with op.batch_alter_table('formulas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_formulas_concept_id'), ['concept_id'], unique=False)

    op.create_table('indicators',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('abbreviation', sa.String(length=100), nullable=True),
    sa.Column('indicator_family', sa.String(length=100), nullable=False),
    sa.Column('formula_text', sa.Text(), nullable=True),
    sa.Column('calculation_method', sa.Text(), nullable=False),
    sa.Column('default_parameters_json', sa.JSON(), nullable=True),
    sa.Column('input_requirements_json', sa.JSON(), nullable=True),
    sa.Column('interpretation', sa.Text(), nullable=False),
    sa.Column('bullish_signals', sa.Text(), nullable=True),
    sa.Column('bearish_signals', sa.Text(), nullable=True),
    sa.Column('suitable_regimes', sa.Text(), nullable=True),
    sa.Column('unsuitable_regimes', sa.Text(), nullable=True),
    sa.Column('strengths', sa.Text(), nullable=True),
    sa.Column('limitations', sa.Text(), nullable=True),
    sa.Column('common_misuse', sa.Text(), nullable=True),
    sa.Column('implementation_notes', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('concept_id')
    )
    op.create_table('knowledge_articles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('subtitle', sa.String(length=500), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('definition', sa.Text(), nullable=True),
    sa.Column('detailed_explanation', sa.Text(), nullable=True),
    sa.Column('historical_background', sa.Text(), nullable=True),
    sa.Column('market_context', sa.Text(), nullable=True),
    sa.Column('trading_applications', sa.Text(), nullable=True),
    sa.Column('risk_considerations', sa.Text(), nullable=True),
    sa.Column('advantages', sa.Text(), nullable=True),
    sa.Column('limitations', sa.Text(), nullable=True),
    sa.Column('common_mistakes', sa.Text(), nullable=True),
    sa.Column('examples', sa.Text(), nullable=True),
    sa.Column('counter_examples', sa.Text(), nullable=True),
    sa.Column('practical_checklist', sa.Text(), nullable=True),
    sa.Column('difficulty_level', sa.String(length=50), nullable=False),
    sa.Column('audience_level', sa.String(length=100), nullable=True),
    sa.Column('language', sa.String(length=20), nullable=False),
    sa.Column('lifecycle_status', sa.String(length=50), nullable=False),
    sa.Column('review_status', sa.String(length=50), nullable=False),
    sa.Column('confidence_score', sa.Float(), nullable=True),
    sa.Column('confidence_method', sa.String(length=255), nullable=True),
    sa.Column('confidence_reason', sa.Text(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)', name='ck_knowledge_articles_confidence_score_range'),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('knowledge_articles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_knowledge_articles_concept_id'), ['concept_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_knowledge_articles_slug'), ['slug'], unique=True)

    op.create_table('patterns',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('pattern_family', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('detection_rules_json', sa.JSON(), nullable=False),
    sa.Column('confirmation_rules_json', sa.JSON(), nullable=True),
    sa.Column('invalidation_rules_json', sa.JSON(), nullable=True),
    sa.Column('suitable_regimes_json', sa.JSON(), nullable=True),
    sa.Column('failure_modes', sa.Text(), nullable=True),
    sa.Column('visual_description', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('concept_id')
    )
    op.create_table('strategies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('strategy_family', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('lifecycle_status', sa.String(length=50), nullable=False),
    sa.Column('review_status', sa.String(length=50), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('eligible_markets_json', sa.JSON(), nullable=True),
    sa.Column('eligible_instruments_json', sa.JSON(), nullable=True),
    sa.Column('timeframes_json', sa.JSON(), nullable=True),
    sa.Column('required_data_json', sa.JSON(), nullable=True),
    sa.Column('market_regimes_json', sa.JSON(), nullable=True),
    sa.Column('entry_rules_json', sa.JSON(), nullable=False),
    sa.Column('exit_rules_json', sa.JSON(), nullable=False),
    sa.Column('invalidation_rules_json', sa.JSON(), nullable=False),
    sa.Column('risk_rules_json', sa.JSON(), nullable=False),
    sa.Column('filters_json', sa.JSON(), nullable=True),
    sa.Column('parameter_schema_json', sa.JSON(), nullable=True),
    sa.Column('known_weaknesses', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('concept_id')
    )
    op.create_table('claim_conflicts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('claim_a_id', sa.Integer(), nullable=False),
    sa.Column('claim_b_id', sa.Integer(), nullable=False),
    sa.Column('conflict_type', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('resolution', sa.Text(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('claim_a_id < claim_b_id', name='ck_claim_conflicts_canonical_pair'),
    sa.CheckConstraint('claim_a_id <> claim_b_id', name='ck_claim_conflicts_not_self'),
    sa.ForeignKeyConstraint(['claim_a_id'], ['claims.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['claim_b_id'], ['claims.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('claim_a_id', 'claim_b_id', name='uq_claim_conflict_pair')
    )
    with op.batch_alter_table('claim_conflicts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_claim_conflicts_claim_a_id'), ['claim_a_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_claim_conflicts_claim_b_id'), ['claim_b_id'], unique=False)

    op.create_table('faqs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('article_id', sa.Integer(), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('answer', sa.Text(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('difficulty_level', sa.String(length=50), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('position >= 0', name='ck_faqs_position_nonnegative'),
    sa.ForeignKeyConstraint(['article_id'], ['knowledge_articles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('article_id', 'position', name='uq_faq_position')
    )
    with op.batch_alter_table('faqs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_faqs_article_id'), ['article_id'], unique=False)

    op.create_table('instruments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('asset_class_id', sa.Integer(), nullable=False),
    sa.Column('canonical_symbol', sa.String(length=100), nullable=False),
    sa.Column('display_name', sa.String(length=500), nullable=False),
    sa.Column('base_asset', sa.String(length=100), nullable=True),
    sa.Column('quote_asset', sa.String(length=100), nullable=True),
    sa.Column('instrument_type', sa.String(length=100), nullable=False),
    sa.Column('venue', sa.String(length=255), nullable=True),
    sa.Column('contract_type', sa.String(length=100), nullable=True),
    sa.Column('contract_size', sa.Float(), nullable=True),
    sa.Column('tick_size', sa.Float(), nullable=True),
    sa.Column('tick_value', sa.Float(), nullable=True),
    sa.Column('price_precision', sa.Integer(), nullable=True),
    sa.Column('volume_min', sa.Float(), nullable=True),
    sa.Column('volume_max', sa.Float(), nullable=True),
    sa.Column('volume_step', sa.Float(), nullable=True),
    sa.Column('trading_hours', sa.Text(), nullable=True),
    sa.Column('timezone', sa.String(length=100), nullable=True),
    sa.Column('settlement_type', sa.String(length=100), nullable=True),
    sa.Column('expiry_behavior', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['asset_class_id'], ['asset_classes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('canonical_symbol', 'venue', name='uq_instrument_symbol_venue'),
    sa.UniqueConstraint('concept_id')
    )
    with op.batch_alter_table('instruments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_instruments_asset_class_id'), ['asset_class_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_instruments_canonical_symbol'), ['canonical_symbol'], unique=False)

    op.create_table('knowledge_sections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('article_id', sa.Integer(), nullable=False),
    sa.Column('section_type', sa.String(length=50), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('position >= 0', name='ck_knowledge_sections_position_nonnegative'),
    sa.ForeignKeyConstraint(['article_id'], ['knowledge_articles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('article_id', 'position', name='uq_knowledge_section_position')
    )
    with op.batch_alter_table('knowledge_sections', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_knowledge_sections_article_id'), ['article_id'], unique=False)

    op.create_table('case_studies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('instrument_id', sa.Integer(), nullable=True),
    sa.Column('strategy_id', sa.Integer(), nullable=True),
    sa.Column('event_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('market_regime', sa.String(length=100), nullable=True),
    sa.Column('context', sa.Text(), nullable=False),
    sa.Column('available_information', sa.Text(), nullable=True),
    sa.Column('decision_options', sa.Text(), nullable=True),
    sa.Column('chosen_decision', sa.Text(), nullable=True),
    sa.Column('outcome', sa.Text(), nullable=True),
    sa.Column('lessons', sa.Text(), nullable=False),
    sa.Column('data_snapshot_reference', sa.String(length=1000), nullable=True),
    sa.Column('review_status', sa.String(length=50), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('case_studies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_case_studies_concept_id'), ['concept_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_case_studies_instrument_id'), ['instrument_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_case_studies_strategy_id'), ['strategy_id'], unique=False)

    with op.batch_alter_table('claims', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'lifecycle_status',
            sa.String(length=50),
            nullable=False,
            server_default='draft',
        ))
        batch_op.add_column(sa.Column('confidence_method', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('confidence_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('last_reviewed_at', sa.DateTime(timezone=True), nullable=True))
def downgrade() -> None:
    """Remove Pack 2C tables and restore the Pack 2B claim schema."""
    with op.batch_alter_table('claims', schema=None) as batch_op:
        batch_op.drop_column('last_reviewed_at')
        batch_op.drop_column('confidence_reason')
        batch_op.drop_column('confidence_method')
        batch_op.drop_column('lifecycle_status')

    with op.batch_alter_table('case_studies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_case_studies_strategy_id'))
        batch_op.drop_index(batch_op.f('ix_case_studies_instrument_id'))
        batch_op.drop_index(batch_op.f('ix_case_studies_concept_id'))

    op.drop_table('case_studies')
    with op.batch_alter_table('knowledge_sections', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_knowledge_sections_article_id'))

    op.drop_table('knowledge_sections')
    with op.batch_alter_table('instruments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_instruments_canonical_symbol'))
        batch_op.drop_index(batch_op.f('ix_instruments_asset_class_id'))

    op.drop_table('instruments')
    with op.batch_alter_table('faqs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_faqs_article_id'))

    op.drop_table('faqs')
    with op.batch_alter_table('claim_conflicts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_claim_conflicts_claim_b_id'))
        batch_op.drop_index(batch_op.f('ix_claim_conflicts_claim_a_id'))

    op.drop_table('claim_conflicts')
    op.drop_table('strategies')
    op.drop_table('patterns')
    with op.batch_alter_table('knowledge_articles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_knowledge_articles_slug'))
        batch_op.drop_index(batch_op.f('ix_knowledge_articles_concept_id'))

    op.drop_table('knowledge_articles')
    op.drop_table('indicators')
    with op.batch_alter_table('formulas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_formulas_concept_id'))

    op.drop_table('formulas')
    op.drop_table('economic_event_types')
    with op.batch_alter_table('concept_aliases', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_concept_aliases_normalized_alias'))
        batch_op.drop_index(batch_op.f('ix_concept_aliases_concept_id'))

    op.drop_table('concept_aliases')
    op.drop_table('asset_classes')
    with op.batch_alter_table('source_assessments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_source_assessments_source_id'))

    op.drop_table('source_assessments')
    with op.batch_alter_table('knowledge_revisions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_knowledge_revisions_entity_type'))
        batch_op.drop_index(batch_op.f('ix_knowledge_revisions_entity_id'))

    op.drop_table('knowledge_revisions')
    with op.batch_alter_table('knowledge_reviews', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_knowledge_reviews_entity_type'))
        batch_op.drop_index(batch_op.f('ix_knowledge_reviews_entity_id'))

    op.drop_table('knowledge_reviews')
